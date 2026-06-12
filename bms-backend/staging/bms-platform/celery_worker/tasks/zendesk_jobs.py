"""
Zendesk bulk job lifecycle — replaces the PHP cron_jobs/Bulk_zendesk.php.

Two periodic tasks:
  1. create_zendesk_jobs  — picks up Pending/queued operations and submits
                             batches of up to 90 rows to the Zendesk bulk API.
  2. check_zendesk_jobs_status — polls all queued/working Zendesk jobs,
                                  updates row statuses, marks operations complete,
                                  and emails the submitter.

Both tasks use psycopg2 (sync) since Celery tasks are synchronous.
The ZendeskClient is invoked via asyncio.run() for HTTP calls.
"""
import asyncio
import json
import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import psycopg2
import psycopg2.extras
import structlog

from celery_worker.celery_app import app

logger = structlog.get_logger()

MAX_CONCURRENT_JOBS = 27   # max Zendesk jobs in flight at once
BATCH_SIZE = 90             # rows per Zendesk bulk job (Zendesk limit is 100)
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def _get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_client(subdomain: str, email: str, access_token: str):
    from app.zendesk.services.zendesk_client import ZendeskClient
    return ZendeskClient(subdomain, email, access_token)


async def _bulk_create(client, tickets_payload: dict) -> dict:
    return await client.bulk_create_tickets(tickets_payload)


async def _bulk_delete(client, ticket_ids: list[int]) -> dict:
    return await client.bulk_delete_tickets(ticket_ids)


async def _poll_job(client, job_url: str) -> dict:
    return await client.get_job_status(job_url)


def _build_create_payload(csv_rows: list[dict], operation: dict) -> dict:
    """Build the Zendesk bulk ticket creation JSON payload."""
    import json as _json

    mappings = _json.loads(operation["mappings"] or "{}")
    headers = _json.loads(operation["headers"] or "[]")

    # Locate requester name/email columns
    req_name_col = next((i for i, h in enumerate(headers) if h == "Requester Name"), None)
    req_email_col = next((i for i, h in enumerate(headers) if h == "Requester Email"), None)

    # Load process-level config from DB (done before calling this function;
    # passed via operation dict enriched by the caller)
    process_fields = operation.get("_process_fields", {})   # field_id -> {type, default_value, user_visible}
    ticket_form_id = operation.get("ticket_form_id") or 0
    ticket_group_id = operation.get("ticket_group_id") or 0
    tags = operation.get("_tags", [])

    tickets = []
    for row in csv_rows:
        ticket = {}
        custom_fields = []

        for field_id_str, col_idx in mappings.items():
            pf = process_fields.get(int(field_id_str))
            if not pf:
                continue

            ftype = pf["type"]
            col_key = f"col_{col_idx}"
            value = row.get(col_key, "") if pf["user_visible"] else pf["default_value"]

            if ftype == "subject":
                ticket["subject"] = value
            elif ftype == "description":
                ticket["comment"] = {"body": value}
            elif ftype == "status":
                ticket["status"] = value
            elif ftype == "priority":
                ticket["priority"] = value
            elif ftype == "tickettype":
                ticket["type"] = value
            else:
                custom_fields.append({"id": int(field_id_str), "value": value})

        # Append hidden fields not in user mapping
        for field_id, pf in process_fields.items():
            if str(field_id) not in mappings and pf["type"] not in ("subject", "description", "status", "priority", "tickettype"):
                custom_fields.append({"id": field_id, "value": pf["default_value"]})

        ticket["custom_fields"] = custom_fields
        if ticket_form_id:
            ticket["ticket_form_id"] = ticket_form_id
        if ticket_group_id:
            ticket["group_id"] = ticket_group_id

        ticket["tags"] = tags
        ticket["public"] = True

        name_key = f"col_{req_name_col}" if req_name_col is not None else None
        email_key = f"col_{req_email_col}" if req_email_col is not None else None
        ticket["requester"] = {
            "name": row.get(name_key, "Unknown") if name_key else "Unknown",
            "email": row.get(email_key, "") if email_key else "",
        }
        tickets.append(ticket)

    return {"tickets": tickets}


def _send_completion_email(to_email: str, operation: dict, status: str):
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    from_addr = os.environ.get("SMTP_FROM", smtp_user)

    if not smtp_host or not to_email:
        return

    op_type = "Creation" if operation.get("operation_type") == "create" else "Deletion"
    subject = f"Zendesk Operation ID {operation['id']} {status.title()}"
    body = (
        f"Your Zendesk Bulk Job has {status}.<br><br>"
        f"Operation ID: <b>{operation['id']}</b><br>"
        f"Operation Type: <b>Ticket {op_type}</b><br>"
        f"Instance: <b>{operation.get('instance_name', '')} [{operation.get('subdomain', '')}]</b><br>"
        f"Process: <b>{operation.get('process_name', '')}</b><br>"
        f"Items processed: <b>{operation.get('processed_count', 0)}</b><br><br>"
        "Kind Regards,<br>BMS Team"
    )

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_email], msg.as_string())
    except Exception as e:
        logger.warning("email_send_failed", error=str(e))


# ── Task 1: submit pending operations to Zendesk ─────────────────────────────

@app.task(name="zendesk.create_jobs", bind=True, max_retries=3)
def create_zendesk_jobs(self):
    """
    Picks up Pending/queued operations for today, batches rows,
    submits to Zendesk bulk API, saves job IDs.
    """
    today = date.today().isoformat()
    conn = _get_conn()
    try:
        cur = conn.cursor()

        # Check running job count
        cur.execute("SELECT COUNT(*) AS cnt FROM zd_jobs WHERE status IN ('queued', 'working')")
        running = cur.fetchone()["cnt"]
        if running >= MAX_CONCURRENT_JOBS:
            logger.info("zendesk_jobs_at_capacity", running=running)
            return

        cur.execute(
            """
            SELECT o.*, i.subdomain, i.email, i.access_token,
                   p.operation AS operation_type,
                   p.ticket_form_id, p.ticket_group_id
            FROM zd_operations o
            JOIN zd_instances i ON i.id = o.zendesk_instance_id
            JOIN zd_processes p ON p.id = o.process_id
            WHERE o.start_date = %s AND o.status IN ('Pending', 'queued', 'working')
            ORDER BY o.id ASC
            """,
            (today,),
        )
        operations = cur.fetchall()

        created_jobs = 0

        for operation in operations:
            operation = dict(operation)
            op_id = operation["id"]

            # Load process fields
            cur.execute(
                """
                SELECT pf.field_id, zf.type, pf.default_value, pf.user_visible
                FROM zd_process_fields pf
                JOIN zd_fields zf ON zf.id = pf.field_id
                WHERE pf.process_id = %s
                """,
                (operation["process_id"],),
            )
            operation["_process_fields"] = {
                r["field_id"]: dict(r) for r in cur.fetchall()
            }

            # Load tags
            cur.execute("SELECT tags FROM zd_process_tags WHERE process_id = %s", (operation["process_id"],))
            tags_row = cur.fetchone()
            operation["_tags"] = json.loads(tags_row["tags"]) if tags_row else []

            while created_jobs < MAX_CONCURRENT_JOBS:
                # Fetch next unprocessed batch
                cur.execute(
                    """
                    SELECT * FROM zd_operation_rows
                    WHERE operation_id = %s AND job_id IS NULL
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    (op_id, BATCH_SIZE),
                )
                batch = cur.fetchall()

                if not batch:
                    cur.execute(
                        "UPDATE zd_operations SET status = 'Processing' WHERE id = %s AND status = 'Pending'",
                        (op_id,),
                    )
                    conn.commit()
                    break

                client = _get_client(operation["subdomain"], operation["email"], operation["access_token"])

                try:
                    if operation["operation_type"] == "create":
                        payload = _build_create_payload([dict(r) for r in batch], operation)
                        result = asyncio.run(_bulk_create(client, payload))
                    else:
                        mappings = json.loads(operation["mappings"] or "{}")
                        del_col = int(mappings.get("delete_column", 0))
                        ids = [int(r[f"col_{del_col}"]) for r in batch if r.get(f"col_{del_col}")]
                        result = asyncio.run(_bulk_delete(client, ids))
                except Exception as exc:
                    logger.error("zendesk_submit_error", op_id=op_id, error=str(exc))
                    break

                job_status = result.get("job_status", {})
                job_id = job_status.get("id")
                if not job_id:
                    logger.warning("zendesk_no_job_id", op_id=op_id, result=result)
                    break

                cur.execute(
                    """
                    INSERT INTO zd_jobs (operation_id, zendesk_job_id, status, url, progress, total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        op_id, job_id,
                        job_status.get("status", "queued"),
                        job_status.get("url", ""),
                        job_status.get("progress", 0),
                        job_status.get("total", len(batch)),
                    ),
                )

                # Stamp rows with job_id + index
                update_cases = " ".join(f"WHEN id = {r['id']} THEN {i}" for i, r in enumerate(batch))
                row_ids = ", ".join(str(r["id"]) for r in batch)
                cur.execute(
                    f"""
                    UPDATE zd_operation_rows
                    SET job_id = %s,
                        job_index = CASE {update_cases} END
                    WHERE id IN ({row_ids})
                    """,
                    (job_id,),
                )
                conn.commit()
                created_jobs += 1

    except Exception as exc:
        logger.exception("create_zendesk_jobs_error", error=str(exc))
        conn.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        conn.close()


# ── Task 2: poll job statuses and update rows ─────────────────────────────────

@app.task(name="zendesk.check_job_status", bind=True, max_retries=3)
def check_zendesk_jobs_status(self):
    """
    Polls all queued/working Zendesk jobs.
    Updates row-level status (ticket_id for creates, status text for deletes).
    Marks operations completed/failed and emails submitter.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT zj.*, i.subdomain, i.email, i.access_token,
                   p.operation AS operation_type,
                   o.item_count
            FROM zd_jobs zj
            JOIN zd_operations o ON o.id = zj.operation_id
            JOIN zd_instances i  ON i.id = o.zendesk_instance_id
            JOIN zd_processes p  ON p.id = o.process_id
            WHERE zj.status IN ('queued', 'working')
            """,
        )
        jobs = cur.fetchall()

        for job in jobs:
            job = dict(job)
            client = _get_client(job["subdomain"], job["email"], job["access_token"])
            try:
                result = asyncio.run(_poll_job(client, job["url"]))
            except Exception as exc:
                logger.warning("poll_job_error", job_id=job["zendesk_job_id"], error=str(exc))
                continue

            js = result.get("job_status", {})
            new_status = js.get("status", job["status"])
            new_progress = int(js.get("progress") or 0)

            cur.execute(
                "UPDATE zd_jobs SET status = %s, progress = %s WHERE id = %s",
                (new_status, new_progress, job["id"]),
            )

            # Aggregate progress for this operation
            cur.execute(
                "SELECT COALESCE(SUM(progress), 0) AS total_progress FROM zd_jobs WHERE operation_id = %s",
                (job["operation_id"],),
            )
            total_progress = cur.fetchone()["total_progress"]

            # Update row-level statuses
            if new_status in ("completed", "working"):
                results = js.get("results") or []
                if job["operation_type"] == "create" and results:
                    update_cases = " ".join(
                        f"WHEN job_index = {r['index']} THEN '{r['id']}'" for r in results if "index" in r and "id" in r
                    )
                    row_indices = ", ".join(str(r["index"]) for r in results if "index" in r)
                    if update_cases and row_indices:
                        cur.execute(
                            f"""
                            UPDATE zd_operation_rows
                            SET status = 'completed', ticket_id = CASE {update_cases} END
                            WHERE job_id = %s AND job_index IN ({row_indices})
                            """,
                            (job["zendesk_job_id"],),
                        )
                elif job["operation_type"] == "delete" and results:
                    update_cases = " ".join(
                        f"WHEN job_index = {i} THEN '{'Failed: ' + str(r.get('errors', '')) if r.get('status') == 'failed' else r.get('status', 'Deleted')}'"
                        for i, r in enumerate(results)
                    )
                    row_indices = ", ".join(str(i) for i in range(len(results)))
                    if update_cases:
                        cur.execute(
                            f"""
                            UPDATE zd_operation_rows
                            SET status = CASE {update_cases} END
                            WHERE job_id = %s AND job_index IN ({row_indices})
                            """,
                            (job["zendesk_job_id"],),
                        )

            # Determine if operation is fully done
            item_count = job["item_count"]
            is_done = total_progress >= item_count and new_status == "completed"
            is_failed = new_status == "failed"

            if is_done:
                cur.execute(
                    "UPDATE zd_operations SET status = 'completed', processed_count = %s, updated_at = NOW() WHERE id = %s",
                    (total_progress, job["operation_id"]),
                )
            elif is_failed:
                cur.execute(
                    "UPDATE zd_operations SET status = 'failed', updated_at = NOW() WHERE id = %s",
                    (job["operation_id"],),
                )
            else:
                cur.execute(
                    "UPDATE zd_operations SET processed_count = %s, updated_at = NOW() WHERE id = %s",
                    (total_progress, job["operation_id"]),
                )

            conn.commit()

            # Email on completion or failure
            if is_done or is_failed:
                cur.execute(
                    """
                    SELECT o.id, o.processed_count, i.instance_name, i.subdomain,
                           p.process_name, p.operation AS operation_type,
                           u.email AS creator_email
                    FROM zd_operations o
                    JOIN zd_instances i ON i.id = o.zendesk_instance_id
                    JOIN zd_processes p ON p.id = o.process_id
                    LEFT JOIN users u   ON u.id = o.created_by
                    WHERE o.id = %s
                    """,
                    (job["operation_id"],),
                )
                op_detail = dict(cur.fetchone() or {})
                to_email = op_detail.pop("creator_email", None)
                _send_completion_email(to_email, op_detail, new_status)

    except Exception as exc:
        logger.exception("check_zendesk_jobs_error", error=str(exc))
        conn.rollback()
        raise self.retry(exc=exc, countdown=30)
    finally:
        conn.close()
