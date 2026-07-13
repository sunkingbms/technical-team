"""
Operation lifecycle: create (validate + pull sheet data + persist rows),
cancel, and row-level progress lookups.
"""
import asyncpg

from app.zendesk import operation_repository as repo
from app.zendesk.services.sheets_client import fetch_sheet_data
from core.exceptions import BadRequestError, ErrorCodes, NotFoundError


async def list_operations(conn: asyncpg.Connection, skip: int = 0, limit: int = 50) -> dict:
    return await repo.list_operations(conn, skip=skip, limit=limit)


async def get_operation(conn: asyncpg.Connection, operation_id: int) -> dict:
    return await repo.get_operation(conn, operation_id)


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
    # Validate instance + process exist and are compatible
    process = await repo.get_process_for_operation(conn, process_id)
    if not process:
        raise NotFoundError(message="Process not found", code=ErrorCodes.TASK_NOT_FOUND)
    if process["zendesk_instance_id"] != instance_id:
        raise BadRequestError(message="Process does not belong to the given instance", code=ErrorCodes.BAD_REQUEST)

    # Validate mapping for delete operations
    if process["operation"] == "delete":
        if "delete_column" not in field_mapping:
            raise BadRequestError(message="delete_column is required for delete processes", code=ErrorCodes.BAD_REQUEST)

    # Fetch sheet data
    sheet_data = await fetch_sheet_data(sheet_id, sheet_name)
    headers = sheet_data["headers"]
    rows = sheet_data["rows"]

    # Validate delete column values are numeric ticket IDs
    if process["operation"] == "delete":
        col_idx = int(field_mapping["delete_column"])
        col_key = headers[col_idx] if col_idx < len(headers) else None
        invalid_rows = []
        for i, row in enumerate(rows, start=2):
            try:
                val = row.get(col_key, "") if col_key else ""
                if not str(val).strip().isdigit():
                    invalid_rows.append(f"Row {i}: '{val}'")
            except (KeyError, TypeError):
                invalid_rows.append(f"Row {i}: missing value")
            if len(invalid_rows) >= 10:
                break
        if invalid_rows:
            raise BadRequestError(
                message="Invalid ticket IDs in delete column:\n" + "\n".join(invalid_rows),
                code=ErrorCodes.VALIDATION_ERROR,
            )

    operation_id = await repo.insert_operation(
        conn, instance_id, process_id, start_date, len(rows), field_mapping, headers, created_by
    )
    await repo.insert_operation_rows(conn, operation_id, process_id, headers, rows)

    return await repo.get_operation(conn, operation_id)


async def cancel_operation(conn: asyncpg.Connection, operation_id: int) -> None:
    op = await repo.get_operation(conn, operation_id)
    if op["status"] not in ("Pending", "queued"):
        raise BadRequestError(
            message="Only Pending or queued operations can be cancelled",
            code=ErrorCodes.BAD_REQUEST,
        )
    await repo.cancel_operation(conn, operation_id)


async def get_operation_rows(conn: asyncpg.Connection, operation_id: int, skip: int = 0, limit: int = 100) -> dict:
    await repo.get_operation(conn, operation_id)  # 404 guard
    return await repo.get_operation_rows(conn, operation_id, skip=skip, limit=limit)
