"""
Operation lifecycle: create, cancel, status, row-level progress.
"""
import asyncpg

from app.database.query import fetch, fetch_row
from app.zendesk.services.sheets_client import fetch_sheet_data
from core.exceptions import BadRequestError, ErrorCodes, NotFoundError


async def _get_operation(conn: asyncpg.Connection, operation_id: int) -> dict:
    row = await fetch_row(
        conn,
        """
        SELECT o.*, i.instance_name, p.operation AS operation_type,
               u.email AS created_by_email
        FROM zd_operations o
        JOIN zd_instances i ON i.id = o.zendesk_instance_id
        JOIN zd_processes p ON p.id = o.process_id
        LEFT JOIN users u   ON u.id  = o.created_by
        WHERE o.id = $1
        """,
        operation_id,
        label="operations:get",
    )
    if not row:
        raise NotFoundError("Operation not found", ErrorCodes.TASK_NOT_FOUND)
    return dict(row)


async def list_operations(
    conn: asyncpg.Connection, skip: int = 0, limit: int = 50
) -> dict:
    total = await conn.fetchval("SELECT COUNT(*) FROM zd_operations")
    rows = await fetch(
        conn,
        """
        SELECT o.id, o.zendesk_instance_id, o.process_id, o.status,
               o.item_count, o.processed_count, o.start_date, o.created_at,
               i.instance_name, p.operation AS operation_type,
               u.email AS created_by_email
        FROM zd_operations o
        JOIN zd_instances i ON i.id = o.zendesk_instance_id
        JOIN zd_processes p ON p.id = o.process_id
        LEFT JOIN users u   ON u.id  = o.created_by
        ORDER BY o.id DESC
        LIMIT $1 OFFSET $2
        """,
        limit, skip,
        label="operations:list",
    )
    return {"total": total, "items": [dict(r) for r in rows]}


async def get_operation(conn: asyncpg.Connection, operation_id: int) -> dict:
    return await _get_operation(conn, operation_id)


async def create_operation(
    conn: asyncpg.Connection,
    instance_id: int,
    process_id: int,
    start_date,
    sheet_id: str,
    sheet_name: str,
    field_mapping: dict,
    created_by: int,
) -> dict:
    import json

    # Validate instance + process exist and are compatible
    process = await fetch_row(
        conn,
        "SELECT id, operation, instance_id FROM zd_processes WHERE id = $1 AND NOT is_deleted",
        process_id,
        label="operations:validate_process",
    )
    if not process:
        raise NotFoundError("Process not found", ErrorCodes.TASK_NOT_FOUND)
    if process["instance_id"] != instance_id:
        raise BadRequestError("Process does not belong to the given instance", ErrorCodes.BAD_REQUEST)

    # Validate mapping for delete operations
    if process["operation"] == "delete":
        if "delete_column" not in field_mapping:
            raise BadRequestError("delete_column is required for delete processes", ErrorCodes.BAD_REQUEST)

    # Fetch sheet data
    sheet_data = await fetch_sheet_data(sheet_id, sheet_name)
    headers = sheet_data["headers"]
    rows = sheet_data["rows"]

    # Validate delete column values are numeric ticket IDs
    if process["operation"] == "delete":
        col_idx = int(field_mapping["delete_column"])
        invalid_rows = []
        for i, row in enumerate(rows, start=2):
            try:
                val = row[col_idx] if col_idx < len(row) else ""
                if not str(val).strip().isdigit():
                    invalid_rows.append(f"Row {i}: '{val}'")
            except (IndexError, TypeError):
                invalid_rows.append(f"Row {i}: missing value")
            if len(invalid_rows) >= 10:
                break
        if invalid_rows:
            raise BadRequestError(
                "Invalid ticket IDs in delete column:\n" + "\n".join(invalid_rows),
                ErrorCodes.VALIDATION_ERROR,
            )

    # Save operation
    op_row = await conn.fetchrow(
        """
        INSERT INTO zd_operations
            (zendesk_instance_id, process_id, start_date, item_count, mappings, headers, created_by)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
        RETURNING id
        """,
        instance_id, process_id, start_date,
        len(rows),
        json.dumps(field_mapping),
        json.dumps(headers),
        created_by,
    )
    operation_id = op_row["id"]

    # Bulk-insert rows
    col_names = ["operation_id", "process_id"] + [f"col_{i}" for i in range(20)]
    records = []
    for row in rows:
        padded = list(row) + [None] * (20 - len(row))
        records.append((operation_id, process_id, *padded[:20]))

    await conn.executemany(
        f"""
        INSERT INTO zd_operation_rows ({', '.join(col_names)})
        VALUES ({', '.join(f'${i+1}' for i in range(len(col_names)))})
        """,
        records,
    )

    return await _get_operation(conn, operation_id)


async def cancel_operation(conn: asyncpg.Connection, operation_id: int) -> None:
    op = await _get_operation(conn, operation_id)
    if op["status"] not in ("Pending", "queued"):
        raise BadRequestError(
            "Only Pending or queued operations can be cancelled",
            ErrorCodes.BAD_REQUEST,
        )
    async with conn.transaction():
        await conn.execute("DELETE FROM zd_jobs WHERE operation_id = $1", operation_id)
        await conn.execute("DELETE FROM zd_operation_rows WHERE operation_id = $1", operation_id)
        await conn.execute("DELETE FROM zd_operations WHERE id = $1", operation_id)


async def get_operation_rows(
    conn: asyncpg.Connection, operation_id: int, skip: int = 0, limit: int = 100
) -> dict:
    await _get_operation(conn, operation_id)  # 404 guard

    total = await conn.fetchval(
        "SELECT COUNT(*) FROM zd_operation_rows WHERE operation_id = $1", operation_id
    )
    rows = await fetch(
        conn,
        """
        SELECT id, status, ticket_id,
               col_0, col_1, col_2, col_3, col_4, col_5, col_6, col_7, col_8, col_9,
               col_10, col_11, col_12, col_13, col_14, col_15, col_16, col_17, col_18, col_19
        FROM zd_operation_rows
        WHERE operation_id = $1
        ORDER BY id ASC
        LIMIT $2 OFFSET $3
        """,
        operation_id, limit, skip,
        label="operation_rows:list",
    )
    items = []
    for r in rows:
        d = dict(r)
        cols = {k: v for k, v in d.items() if k.startswith("col_") and v is not None}
        items.append({"id": d["id"], "status": d["status"], "ticket_id": d["ticket_id"], "columns": cols})

    return {"total": total, "items": items}
