"""
Data access for Zendesk processes: CRUD plus field / tag / form / group
configuration used to build the ticket payload for an operation.
"""
import json

import asyncpg

from app.database.query import execute, fetch, fetch_row, fetchval
from core.exceptions import ErrorCodes, NotFoundError


async def _get_process_raw(conn: asyncpg.Connection, process_id: int) -> dict:
    row = await fetch_row(
        conn,
        "SELECT * FROM zendesk_processes WHERE id = $1 AND NOT is_deleted",
        process_id,
        label="zendesk_processes:get_raw",
    )
    if not row:
        raise NotFoundError(message="Process not found", code=ErrorCodes.TASK_NOT_FOUND)
    return dict(row)


async def list_processes(conn: asyncpg.Connection, instance_id: int) -> list[dict]:
    rows = await fetch(
        conn,
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM zendesk_process_fields pf WHERE pf.process_id = p.id) AS fields_count
        FROM zendesk_processes p
        WHERE p.zendesk_instance_id = $1 AND NOT p.is_deleted
        ORDER BY p.id DESC
        """,
        instance_id,
        label="zendesk_processes:list",
    )
    return [dict(r) for r in rows]


async def get_process(conn: asyncpg.Connection, process_id: int) -> dict:
    row = await fetch_row(
        conn,
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM zendesk_process_fields pf WHERE pf.process_id = p.id) AS fields_count
        FROM zendesk_processes p
        WHERE p.id = $1 AND NOT p.is_deleted
        """,
        process_id,
        label="zendesk_processes:get",
    )
    if not row:
        raise NotFoundError(message="Process not found", code=ErrorCodes.TASK_NOT_FOUND)
    return dict(row)


async def create_process(conn: asyncpg.Connection, instance_id: int, data: dict, created_by: int) -> dict:
    row = await fetch_row(
        conn,
        """
        INSERT INTO zendesk_processes
            (zendesk_instance_id, process_name, process_description, operation, status, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        instance_id,
        data["process_name"],
        data.get("process_description"),
        data["operation"],
        data.get("status", "ACTIVE"),
        created_by,
        label="zendesk_processes:create",
    )
    return {**dict(row), "fields_count": 0}


async def update_process(conn: asyncpg.Connection, process_id: int, data: dict) -> dict:
    await _get_process_raw(conn, process_id)
    fields = {k: v for k, v in data.items() if v is not None}
    if not fields:
        return await get_process(conn, process_id)

    sets, params = [], [process_id]
    for col, val in fields.items():
        params.append(val)
        sets.append(f"{col} = ${len(params)}")
    sets.append("updated_at = NOW()")

    await execute(
        conn,
        f"UPDATE zendesk_processes SET {', '.join(sets)} WHERE id = $1",
        *params,
        label="zendesk_processes:update",
    )
    return await get_process(conn, process_id)


async def delete_process(conn: asyncpg.Connection, process_id: int) -> None:
    await _get_process_raw(conn, process_id)
    await execute(
        conn,
        "UPDATE zendesk_processes SET is_deleted = TRUE WHERE id = $1",
        process_id,
        label="zendesk_processes:delete",
    )


# ── field configuration ───────────────────────────────────────────────────────

async def get_process_fields(conn: asyncpg.Connection, process_id: int) -> list[dict]:
    """Fields already attached to the process, joined with their Zendesk field metadata."""
    rows = await fetch(
        conn,
        """
        SELECT pf.id, pf.field_id, zf.zendesk_field_id, zf.title, zf.type,
               pf.default_value, pf.user_visible, zf.raw_data
        FROM zendesk_process_fields pf
        JOIN zendesk_fields zf ON zf.id = pf.field_id
        WHERE pf.process_id = $1
        ORDER BY pf.id
        """,
        process_id,
        label="zendesk_process_fields:list",
    )
    return [dict(r) for r in rows]


async def get_process_tags(conn: asyncpg.Connection, process_id: int) -> list[str] | None:
    row = await fetch_row(
        conn,
        "SELECT tags FROM zendesk_process_tags WHERE process_id = $1",
        process_id,
        label="zendesk_process_tags:get",
    )
    if not row:
        return None
    return row["tags"]


async def get_instance_forms(conn: asyncpg.Connection, instance_id: int) -> list[dict]:
    rows = await fetch(
        conn,
        "SELECT zendesk_form_id, name FROM zendesk_forms WHERE zendesk_instance_id = $1 ORDER BY name",
        instance_id,
        label="zendesk_forms:list_for_process",
    )
    return [dict(r) for r in rows]


async def get_instance_groups(conn: asyncpg.Connection, instance_id: int) -> list[dict]:
    rows = await fetch(
        conn,
        "SELECT zendesk_group_id, name FROM zendesk_groups WHERE zendesk_instance_id = $1 ORDER BY name",
        instance_id,
        label="zendesk_groups:list_for_process",
    )
    return [dict(r) for r in rows]


async def add_field_to_process(conn: asyncpg.Connection, process_id: int, field_id: int) -> None:
    """field_id = zendesk_fields.id (internal PK)."""
    await _get_process_raw(conn, process_id)
    exists = await fetchval(
        conn,
        "SELECT id FROM zendesk_fields WHERE id = $1",
        field_id,
        label="zendesk_fields:exists",
    )
    if not exists:
        raise NotFoundError(message="Field not found", code=ErrorCodes.INSTANCE_NOT_FOUND)

    await execute(
        conn,
        "INSERT INTO zendesk_process_fields (process_id, field_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        process_id, field_id,
        label="zendesk_process_fields:add",
    )


async def update_process_field(
    conn: asyncpg.Connection, process_id: int, field_id: int, default_value, user_visible
) -> None:
    sets, params = [], [process_id, field_id]
    if default_value is not None:
        params.append(default_value)
        sets.append(f"default_value = ${len(params)}")
    if user_visible is not None:
        params.append(user_visible)
        sets.append(f"user_visible = ${len(params)}")
    if not sets:
        return
    await execute(
        conn,
        f"UPDATE zendesk_process_fields SET {', '.join(sets)} WHERE process_id = $1 AND field_id = $2",
        *params,
        label="zendesk_process_fields:update",
    )


async def remove_field_from_process(conn: asyncpg.Connection, process_id: int, field_id: int) -> None:
    await execute(
        conn,
        "DELETE FROM zendesk_process_fields WHERE process_id = $1 AND field_id = $2",
        process_id, field_id,
        label="zendesk_process_fields:remove",
    )


async def get_available_fields(conn: asyncpg.Connection, process_id: int) -> list[dict]:
    """Fields from the instance not yet added to this process."""
    process = await _get_process_raw(conn, process_id)
    rows = await fetch(
        conn,
        """
        SELECT id, zendesk_field_id, title, type, raw_data
        FROM zendesk_fields
        WHERE zendesk_instance_id = $1
          AND id NOT IN (SELECT field_id FROM zendesk_process_fields WHERE process_id = $2)
        ORDER BY title
        """,
        process["zendesk_instance_id"], process_id,
        label="zendesk_fields:available_for_process",
    )
    return [dict(r) for r in rows]


# ── tags ──────────────────────────────────────────────────────────────────────

async def save_tags(conn: asyncpg.Connection, process_id: int, tags: list[str]) -> None:
    await _get_process_raw(conn, process_id)
    await execute(
        conn,
        """
        INSERT INTO zendesk_process_tags (process_id, tags)
        VALUES ($1, $2::jsonb)
        ON CONFLICT (process_id) DO UPDATE SET tags = EXCLUDED.tags
        """,
        process_id, json.dumps(tags),
        label="zendesk_process_tags:save",
    )


# ── form / group assignment ───────────────────────────────────────────────────

async def set_ticket_form(conn: asyncpg.Connection, process_id: int, form_id: int | None) -> None:
    await _get_process_raw(conn, process_id)
    await execute(
        conn,
        "UPDATE zendesk_processes SET ticket_form_id = $2, updated_at = NOW() WHERE id = $1",
        process_id, form_id,
        label="zendesk_processes:set_form",
    )


async def set_ticket_group(conn: asyncpg.Connection, process_id: int, group_id: int | None) -> None:
    await _get_process_raw(conn, process_id)
    await execute(
        conn,
        "UPDATE zendesk_processes SET ticket_group_id = $2, updated_at = NOW() WHERE id = $1",
        process_id, group_id,
        label="zendesk_processes:set_group",
    )
