"""
Data access for Zendesk operations (one run of a process) and their row-level
data imported from Google Sheets.
"""
import json

import asyncpg

from app.database.query import execute, fetch, fetch_row, fetchval
from core.exceptions import ErrorCodes, NotFoundError


def _parse_jsonb(val, default=None):
    """Return val as a Python object. Handles both raw strings (no JSONB codec) and already-parsed values."""
    if val is None:
        return default
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return val  # already parsed by JSONB codec


async def get_operation(conn: asyncpg.Connection, operation_id: int) -> dict:
    row = await fetch_row(
        conn,
        """
        SELECT o.*, i.name AS instance_name,
               p.operation AS operation,
               u.email AS created_by_email
        FROM zendesk_operations o
        JOIN zendesk_instances i ON i.id = o.zendesk_instance_id
        JOIN zendesk_processes p ON p.id = o.process_id
        LEFT JOIN users u        ON u.id = o.created_by
        WHERE o.id = $1
        """,
        operation_id,
        label="zendesk_operations:get",
    )
    if not row:
        raise NotFoundError(message="Operation not found", code=ErrorCodes.TASK_NOT_FOUND)
    d = dict(row)
    d["headers"] = _parse_jsonb(d.get("headers"), default=[])
    return d


async def list_operations(conn: asyncpg.Connection, skip: int = 0, limit: int = 50) -> dict:
    total = await fetchval(conn, "SELECT COUNT(*) FROM zendesk_operations", label="zendesk_operations:count")
    rows = await fetch(
        conn,
        """
        SELECT o.id, o.zendesk_instance_id, o.process_id, o.status,
               o.item_count, o.processed_count, o.start_date, o.created_at,
               o.headers,
               i.name AS instance_name,
               p.operation AS operation,
               u.email AS created_by_email
        FROM zendesk_operations o
        JOIN zendesk_instances i ON i.id = o.zendesk_instance_id
        JOIN zendesk_processes p ON p.id = o.process_id
        LEFT JOIN users u        ON u.id = o.created_by
        ORDER BY o.id DESC
        LIMIT $1 OFFSET $2
        """,
        limit, skip,
        label="zendesk_operations:list",
    )
    items = []
    for r in rows:
        d = dict(r)
        d["headers"] = _parse_jsonb(d.get("headers"), default=[])
        items.append(d)
    return {"total": total, "items": items}


async def get_process_for_operation(conn: asyncpg.Connection, process_id: int) -> dict | None:
    row = await fetch_row(
        conn,
        "SELECT id, operation, zendesk_instance_id, ticket_form_id, ticket_group_id FROM zendesk_processes WHERE id = $1 AND NOT is_deleted",
        process_id,
        label="zendesk_operations:validate_process",
    )
    return dict(row) if row else None


async def insert_operation(
    conn: asyncpg.Connection,
    instance_id: int,
    process_id: int,
    start_date,
    item_count: int,
    field_mapping: dict,
    headers: list,
    created_by: int,
) -> int:
    row = await fetch_row(
        conn,
        """
        INSERT INTO zendesk_operations
            (zendesk_instance_id, process_id, start_date, item_count, mappings, headers, created_by)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
        RETURNING id
        """,
        instance_id, process_id, start_date,
        item_count,
        json.dumps(field_mapping),
        json.dumps(headers),
        created_by,
        label="zendesk_operations:insert",
    )
    return row["id"]


async def insert_operation_rows(
    conn: asyncpg.Connection, operation_id: int, process_id: int, headers: list[str], rows: list[dict]
) -> None:
    col_names = ["operation_id", "process_id"] + [f"col_{i}" for i in range(20)]
    records = []
    for row in rows:
        values = [str(row.get(h, "") or "") for h in headers]
        padded = values + [None] * (20 - len(values))
        records.append((operation_id, process_id, *padded[:20]))

    await conn.executemany(
        f"""
        INSERT INTO zendesk_operation_rows ({', '.join(col_names)})
        VALUES ({', '.join(f'${i + 1}' for i in range(len(col_names)))})
        """,
        records,
    )


async def cancel_operation(conn: asyncpg.Connection, operation_id: int) -> None:
    async with conn.transaction():
        await execute(conn, "DELETE FROM zendesk_jobs WHERE operation_id = $1", operation_id, label="zendesk_jobs:cancel")
        await execute(conn, "DELETE FROM zendesk_operation_rows WHERE operation_id = $1", operation_id, label="zendesk_operation_rows:cancel")
        await execute(conn, "DELETE FROM zendesk_operations WHERE id = $1", operation_id, label="zendesk_operations:cancel")


async def get_operation_rows(conn: asyncpg.Connection, operation_id: int, skip: int = 0, limit: int = 100) -> dict:
    total = await fetchval(
        conn,
        "SELECT COUNT(*) FROM zendesk_operation_rows WHERE operation_id = $1",
        operation_id,
        label="zendesk_operation_rows:count",
    )
    rows = await fetch(
        conn,
        """
        SELECT id, status, ticket_id,
               col_0, col_1, col_2, col_3, col_4, col_5, col_6, col_7, col_8, col_9,
               col_10, col_11, col_12, col_13, col_14, col_15, col_16, col_17, col_18, col_19
        FROM zendesk_operation_rows
        WHERE operation_id = $1
        ORDER BY id ASC
        LIMIT $2 OFFSET $3
        """,
        operation_id, limit, skip,
        label="zendesk_operation_rows:list",
    )
    items = []
    for r in rows:
        d = dict(r)
        cols = {k: v for k, v in d.items() if k.startswith("col_") and v is not None}
        items.append({"id": d["id"], "status": d["status"], "ticket_id": d["ticket_id"], "columns": cols})

    return {"total": total, "items": items}
