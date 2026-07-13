"""
Zendesk bulk job lifecycle.

Two periodic tasks:
  1. create_zendesk_jobs        — picks up Pending/queued operations and submits
                                   batches of up to 90 rows to the Zendesk bulk API.
  2. check_zendesk_jobs_status  — polls all queued/working Zendesk jobs,
                                   updates row statuses, marks operations complete,
                                   and emails the submitter.

Both tasks use psycopg2 (sync) since Celery tasks are synchronous.
The ZendeskClient is invoked via asyncio.run() for HTTP calls.

Zendesk API tokens are stored encrypted (app.zendesk.crypto) — every instance
row fetched here carries `encrypted_api_token` and must be decrypted before
building a ZendeskClient.
"""
import asyncio
import json
import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _parse_json(val, default):
    """Return val if already parsed, otherwise json.loads it. Safe for asyncpg/psycopg2 JSONB columns."""
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str) and val:
        return json.loads(val)
    return default

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

def _get_client(subdomain: str, email: str, encrypted_api_token: str):
    from app.zendesk.crypto import decrypt_token
    from app.zendesk.services.zendesk_client import ZendeskClient
    api_token = decrypt_token(encrypted_api_token)
    return ZendeskClient(subdomain, email, api_token)


async def _bulk_create(client, tickets_payload: dict) -> dict:
    return await client.bulk_create_tickets(tickets_payload)


async def _bulk_delete(client, ticket_ids: list[int]) -> dict:
    return await client.bulk_delete_tickets(ticket_ids)


async def _poll_job(client, job_url: str) -> dict:
    return await client.get_job_status(job_url)


FALLBACK_REQUESTER_EMAIL = os.environ.get("FALLBACK_REQUESTER_EMAIL", "support@example.com")
FALLBACK_REQUESTER_NAME  = os.environ.get("FALLBACK_REQUESTER_NAME",  "Customer")


def _build_create_payload(csv_rows: list[dict], operation: dict) -> dict:
    """Build the Zendesk bulk ticket creation JSON payload."""
    mappings = _parse_json(operation["mappings"], {})
    headers  = _parse_json(operation["headers"],  [])

    # Locate requester name/email columns by header label
    req_name_col  = next((i for i, h in enumerate(headers) if h == "Requester Name"),  None)
    req_email_col = next((i for i, h in enumerate(headers) if h == "Requester Email"), None)

    # Process-level config enriched by the caller
    process_fields  = operation.get("_process_fields", {})  # zendesk_field_id -> {type, default_value, user_visible}
    ticket_form_id  = int(operation.get("ticket_form_id")  or 0)
    ticket_group_id = int(operation.get("ticket_group_id") or 0)
    tags = operation.get("_tags", [])

    tickets = []
    for row in csv_rows:
        ticket: dict = {}
        custom_fields: list = []
        mapped_zd_ids: set = set()

        # ── 1. User-mapped fields (keys are zendesk_field_id strings from mappings) ──
        for zd_id_str, col_idx in mappings.items():
            try:
                zd_id = int(zd_id_str)
            except (ValueError, TypeError):
                continue

            pf = process_fields.get(zd_id)
            if not pf:
                logger.warning("process_field_not_found", zd_id=zd_id, op_id=operation.get("id"))
                continue

            mapped_zd_ids.add(zd_id)
            ftype   = pf["type"]
            col_key = f"col_{col_idx}"

            # user_visible can be "YES"/"NO" (string) or True/False (bool)
            is_visible = str(pf.get("user_visible", "NO")).upper() not in ("NO", "FALSE", "0")
            value = row.get(col_key, "") if is_visible else (pf["default_value"] or "")

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
                custom_fields.append({"id": zd_id, "value": value})

        # ── 2. Default values for process fields not in the user mapping ──
        for zd_id, pf in process_fields.items():
            if zd_id in mapped_zd_ids:
                continue
            ftype = pf["type"]
            val   = pf["default_value"] or ""
            if ftype == "subject":
                ticket.setdefault("subject", val)
            elif ftype == "description":
                ticket.setdefault("comment", {"body": val})
            elif ftype == "status":
                ticket.setdefault("status", val)
            elif ftype == "priority":
                ticket.setdefault("priority", val)
            elif ftype == "tickettype":
                ticket.setdefault("type", val)
            elif val:
                custom_fields.append({"id": zd_id, "value": val})

        ticket["custom_fields"] = custom_fields

        if ticket_form_id:
            ticket["ticket_form_id"] = ticket_form_id
        if ticket_group_id:
            ticket["group_id"] = ticket_group_id
        if tags:
            ticket["tags"] = tags

        # ── 3. Requester — always required by the bulk import endpoint ──
        name_key  = f"col_{req_name_col}"  if req_name_col  is not None else None
        email_key = f"col_{req_email_col}" if req_email_col is not None else None
        req_name  = (row.get(name_key,  "") if name_key  else "").strip() or FALLBACK_REQUESTER_NAME
        req_email = (row.get(email_key, "") if email_key else "").strip() or FALLBACK_REQUESTER_EMAIL
        ticket["requester"] = {"name": req_name, "email": req_email}

        # ── 4. public flag ──
        ticket["public"] = True

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
        cur.execute("SELECT COUNT(*) AS cnt FROM zendesk_jobs WHERE status IN ('queued', 'working')")
        running = cur.fetchone()["cnt"]
        if running >= MAX_CONCURRENT_JOBS:
            logger.info("zendesk_jobs_at_capacity", running=running)
            return

        cur.execute(
            """
            SELECT o.*, i.subdomain, i.email, i.encrypted_api_token,
                   p.operation AS operation_type,
                   p.ticket_form_id, p.ticket_group_id
            FROM zendesk_operations o
            JOIN zendesk_instances i ON i.id = o.zendesk_instance_id
            JOIN zendesk_processes p ON p.id = o.process_id
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

            # Load process fields — keyed by zendesk_field_id to match the mappings dict
            cur.execute(
                """
                SELECT pf.field_id, zf.zendesk_field_id, zf.type, pf.default_value, pf.user_visible
                FROM zendesk_process_fields pf
                JOIN zendesk_fields zf ON zf.id = pf.field_id
                WHERE pf.process_id = %s
                """,
                (operation["process_id"],),
            )
            operation["_process_fields"] = {
                r["zendesk_field_id"]: dict(r) for r in cur.fetchall()
            }

            # Load tags
            cur.execute("SELECT tags FROM zendesk_process_tags WHERE process_id = %s", (operation["process_id"],))
            tags_row = cur.fetchone()
            operation["_tags"] = _parse_json(tags_row["tags"], []) if tags_row else []

            while created_jobs < MAX_CONCURRENT_JOBS:
                # Fetch next unprocessed batch
                cur.execute(
                    """
                    SELECT * FROM zendesk_operation_rows
                    WHERE operation_id = %s AND job_id IS NULL
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    (op_id, BATCH_SIZE),
                )
                batch = cur.fetchall()

                if not batch:
                    cur.execute(
                        "UPDATE zendesk_operations SET status = 'queued' WHERE id = %s AND status = 'Pending'",
                        (op_id,),
                    )
                    conn.commit()
                    break

                client = _get_client(operation["subdomain"], operation["email"], operation["encrypted_api_token"])

                try:
                    if operation["operation_type"] == "create":
                        payload = _build_create_payload([dict(r) for r in batch], operation)
                        logger.info(
                            "zendesk_create_payload",
                            op_id=op_id,
                            ticket_count=len(payload.get("tickets", [])),
                            payload_preview=json.dumps(payload)[:2000],
                        )
                        result = asyncio.run(_bulk_create(client, payload))
                        logger.info(
                            "zendesk_create_response",
                            op_id=op_id,
                            response=json.dumps(result)[:2000],
                        )
                    else:
                        mappings = _parse_json(operation["mappings"], {})
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
                    INSERT INTO zendesk_jobs (operation_id, zendesk_job_id, status, url, progress, total)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        op_id, job_id,
                        job_status.get("status") or "queued",
                        job_status.get("url") or "",
                        job_status.get("progress") or 0,
                        job_status.get("total") or len(batch),
                    ),
                )

                # Stamp rows with job_id + index
                update_cases = " ".join(f"WHEN id = {r['id']} THEN {i}" for i, r in enumerate(batch))
                row_ids = ", ".join(str(r["id"]) for r in batch)
                cur.execute(
                    f"""
                    UPDATE zendesk_operation_rows
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
            SELECT zj.*, i.subdomain, i.email, i.encrypted_api_token,
                   p.operation AS operation_type,
                   o.item_count
            FROM zendesk_jobs zj
            JOIN zendesk_operations o ON o.id = zj.operation_id
            JOIN zendesk_instances i  ON i.id = o.zendesk_instance_id
            JOIN zendesk_processes p  ON p.id = o.process_id
            WHERE zj.status IN ('queued', 'working')
            """,
        )
        jobs = cur.fetchall()

        for job in jobs:
            job = dict(job)
            client = _get_client(job["subdomain"], job["email"], job["encrypted_api_token"])
            try:
                result = asyncio.run(_poll_job(client, job["url"]))
            except Exception as exc:
                logger.warning("poll_job_error", job_id=job["zendesk_job_id"], error=str(exc))
                continue

            js = result.get("job_status", {})
            new_status = js.get("status", job["status"])
            new_progress = int(js.get("progress") or 0)

            cur.execute(
                "UPDATE zendesk_jobs SET status = %s, progress = %s WHERE id = %s",
                (new_status, new_progress, job["id"]),
            )

            # Count remaining active jobs for this operation (after updating current job)
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM zendesk_jobs WHERE operation_id = %s AND status IN ('queued', 'working')",
                (job["operation_id"],),
            )
            remaining_active = cur.fetchone()["cnt"]

            # Sum total (batch sizes, set at insert) to use as processed_count
            cur.execute(
                "SELECT COALESCE(SUM(total), 0) AS total_items FROM zendesk_jobs WHERE operation_id = %s",
                (job["operation_id"],),
            )
            total_items = cur.fetchone()["total_items"]

            results = []
            # Update row-level statuses
            # Note: Zendesk Bulk Import results are positionally ordered — no "index" field.
            # Use enumerate() as the job_index, matching how rows were stamped at submission.
            if new_status in ("completed", "working"):
                results = js.get("results") or []
                if job["operation_type"] == "create" and results:
                    # Separate successful (have an id) from failed rows
                    ok_rows = [(i, r) for i, r in enumerate(results) if r.get("id")]
                    fail_rows = [(i, r) for i, r in enumerate(results) if not r.get("id")]

                    if fail_rows:
                        logger.warning(
                            "zendesk_row_failures",
                            job_id=job["zendesk_job_id"],
                            op_id=job["operation_id"],
                            fail_count=len(fail_rows),
                            failures=json.dumps([r for _, r in fail_rows[:5]])[:1000],
                        )

                    if ok_rows:
                        update_cases = " ".join(
                            f"WHEN job_index = {i} THEN {r['id']}" for i, r in ok_rows
                        )
                        row_indices = ", ".join(str(i) for i, _ in ok_rows)
                        cur.execute(
                            f"""
                            UPDATE zendesk_operation_rows
                            SET status = 'completed', ticket_id = CASE {update_cases} END
                            WHERE job_id = %s AND job_index IN ({row_indices})
                            """,
                            (job["zendesk_job_id"],),
                        )

                    if fail_rows:
                        # Store the error reason in the status column for display in the UI
                        def _err(r):
                            reason = r.get("errors") or r.get("error") or r.get("details") or "Unknown error"
                            return str(reason)[:200].replace("'", "''")  # escape single quotes for SQL

                        fail_cases = " ".join(
                            f"WHEN job_index = {i} THEN 'Failed: {_err(r)}'"
                            for i, r in fail_rows
                        )
                        fail_indices = ", ".join(str(i) for i, _ in fail_rows)
                        cur.execute(
                            f"""
                            UPDATE zendesk_operation_rows
                            SET status = CASE {fail_cases} END
                            WHERE job_id = %s AND job_index IN ({fail_indices})
                            """,
                            (job["zendesk_job_id"],),
                        )

                elif job["operation_type"] == "delete" and results:
                    update_cases = " ".join(
                        f"WHEN job_index = {i} THEN '{'Failed: ' + str(r.get('errors', '')) if r.get('status') == 'failed' else 'Deleted'}'"
                        for i, r in enumerate(results)
                    )
                    row_indices = ", ".join(str(i) for i in range(len(results)))
                    if update_cases:
                        cur.execute(
                            f"""
                            UPDATE zendesk_operation_rows
                            SET status = CASE {update_cases} END
                            WHERE job_id = %s AND job_index IN ({row_indices})
                            """,
                            (job["zendesk_job_id"],),
                        )

            # Determine if operation is fully done:
            # All jobs must be out of active state and the current one completed.
            # We do NOT rely on progress sum because Zendesk sometimes returns null progress
            # for delete jobs even when status is "completed".
            is_done = remaining_active == 0 and new_status == "completed"
            is_failed = new_status == "failed"

            if is_done:
                cur.execute(
                    "UPDATE zendesk_operations SET status = 'completed', processed_count = %s, updated_at = NOW() WHERE id = %s",
                    (total_items, job["operation_id"]),
                )
            elif is_failed:
                cur.execute(
                    "UPDATE zendesk_operations SET status = 'failed', updated_at = NOW() WHERE id = %s",
                    (job["operation_id"],),
                )
            else:
                cur.execute(
                    "UPDATE zendesk_operations SET processed_count = %s, updated_at = NOW() WHERE id = %s",
                    (total_items, job["operation_id"]),
                )

            conn.commit()

            # Email on completion or failure
            if is_done or is_failed:
                cur.execute(
                    """
                    SELECT o.id, o.processed_count, i.name AS instance_name, i.subdomain,
                           p.process_name, p.operation AS operation_type,
                           u.email AS creator_email
                    FROM zendesk_operations o
                    JOIN zendesk_instances i ON i.id = o.zendesk_instance_id
                    JOIN zendesk_processes p ON p.id = o.process_id
                    LEFT JOIN users u        ON u.id = o.created_by
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
