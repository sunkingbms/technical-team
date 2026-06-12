"""
Process CRUD + field / tag / form / group configuration.
"""
import asyncpg

from app.database.query import fetch, fetch_row
from core.exceptions import BadRequestError, ErrorCodes, NotFoundError


async def _get_process_raw(conn: asyncpg.Connection, process_id: int) -> dict:
    row = await fetch_row(
        conn,
        "SELECT * FROM zd_processes WHERE id = $1 AND NOT is_deleted",
        process_id,
        label="processes:get",
    )
    if not row:
        raise NotFoundError("Process not found", ErrorCodes.TASK_NOT_FOUND)
    return dict(row)


async def list_processes(conn: asyncpg.Connection, instance_id: int) -> list[dict]:
    rows = await fetch(
        conn,
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM zd_process_fields pf WHERE pf.process_id = p.id) AS fields_count
        FROM zd_processes p
        WHERE p.instance_id = $1 AND NOT p.is_deleted
        ORDER BY p.id DESC
        """,
        instance_id,
        label="processes:list",
    )
    return [dict(r) for r in rows]


async def get_process(conn: asyncpg.Connection, process_id: int) -> dict:
    row = await fetch_row(
        conn,
        """
        SELECT p.*,
               (SELECT COUNT(*) FROM zd_process_fields pf WHERE pf.process_id = p.id) AS fields_count
        FROM zd_processes p
        WHERE p.id = $1 AND NOT p.is_deleted
        """,
        process_id,
        label="processes:get_detail",
    )
    if not row:
        raise NotFoundError("Process not found", ErrorCodes.TASK_NOT_FOUND)
    return dict(row)


async def create_process(conn: asyncpg.Connection, instance_id: int, data: dict, created_by: int) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO zd_processes (instance_id, process_name, process_description, operation, status, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        instance_id,
        data["process_name"],
        data.get("process_description"),
        data["operation"],
        data.get("status", "ACTIVE"),
        created_by,
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

    await conn.execute(
        f"UPDATE zd_processes SET {', '.join(sets)} WHERE id = $1",
        *params,
    )
    return await get_process(conn, process_id)


async def delete_process(conn: asyncpg.Connection, process_id: int) -> None:
    await _get_process_raw(conn, process_id)
    await conn.execute("UPDATE zd_processes SET is_deleted = TRUE WHERE id = $1", process_id)


# ── field configuration ───────────────────────────────────────────────────────

async def get_process_fields(conn: asyncpg.Connection, process_id: int) -> dict:
    """Returns configured fields + process form/group/tags for the config UI."""
    process = await _get_process_raw(conn, process_id)

    fields = await fetch(
        conn,
        """
        SELECT pf.id, pf.field_id, zf.zendesk_field_id, zf.title, zf.type,
               pf.default_value, pf.user_visible
        FROM zd_process_fields pf
        JOIN zd_fields zf ON zf.id = pf.field_id
        WHERE pf.process_id = $1
        ORDER BY pf.id
        """,
        process_id,
        label="process_fields:list",
    )

    tags_row = await conn.fetchrow(
        "SELECT tags FROM zd_process_tags WHERE process_id = $1", process_id
    )

    forms = await fetch(
        conn,
        "SELECT form_id, form_name FROM zd_forms WHERE zendesk_instance_id = $1 ORDER BY form_name",
        process["instance_id"],
        label="process:forms",
    )
    groups = await fetch(
        conn,
        "SELECT group_id, group_name FROM zd_groups WHERE zendesk_instance_id = $1 ORDER BY group_name",
        process["instance_id"],
        label="process:groups",
    )

    return {
        "fields": [dict(f) for f in fields],
        "tags": tags_row["tags"] if tags_row else [],
        "ticket_form_id": process.get("ticket_form_id"),
        "ticket_group_id": process.get("ticket_group_id"),
        "available_forms": [dict(f) for f in forms],
        "available_groups": [dict(g) for g in groups],
    }


async def add_field_to_process(conn: asyncpg.Connection, process_id: int, field_id: int) -> None:
    """field_id = zd_fields.id (internal PK)."""
    await _get_process_raw(conn, process_id)
    exists = await conn.fetchval("SELECT id FROM zd_fields WHERE id = $1", field_id)
    if not exists:
        raise NotFoundError("Field not found", ErrorCodes.INSTANCE_NOT_FOUND)

    await conn.execute(
        "INSERT INTO zd_process_fields (process_id, field_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        process_id, field_id,
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
    await conn.execute(
        f"UPDATE zd_process_fields SET {', '.join(sets)} WHERE process_id = $1 AND field_id = $2",
        *params,
    )


async def remove_field_from_process(conn: asyncpg.Connection, process_id: int, field_id: int) -> None:
    await conn.execute(
        "DELETE FROM zd_process_fields WHERE process_id = $1 AND field_id = $2",
        process_id, field_id,
    )


async def get_available_fields(conn: asyncpg.Connection, process_id: int) -> list[dict]:
    """Fields from the instance not yet added to this process."""
    process = await _get_process_raw(conn, process_id)
    rows = await fetch(
        conn,
        """
        SELECT id, zendesk_field_id, title, type
        FROM zd_fields
        WHERE zendesk_instance_id = $1
          AND id NOT IN (SELECT field_id FROM zd_process_fields WHERE process_id = $2)
        ORDER BY title
        """,
        process["instance_id"], process_id,
        label="process:available_fields",
    )
    return [dict(r) for r in rows]


# ── tags ──────────────────────────────────────────────────────────────────────

async def save_tags(conn: asyncpg.Connection, process_id: int, tags: list[str]) -> None:
    import json
    await _get_process_raw(conn, process_id)
    await conn.execute(
        """
        INSERT INTO zd_process_tags (process_id, tags)
        VALUES ($1, $2::jsonb)
        ON CONFLICT (process_id) DO UPDATE SET tags = EXCLUDED.tags
        """,
        process_id, json.dumps(tags),
    )


# ── form / group assignment ───────────────────────────────────────────────────

async def set_ticket_form(conn: asyncpg.Connection, process_id: int, form_id: int | None) -> None:
    await _get_process_raw(conn, process_id)
    await conn.execute(
        "UPDATE zd_processes SET ticket_form_id = $2, updated_at = NOW() WHERE id = $1",
        process_id, form_id,
    )


async def set_ticket_group(conn: asyncpg.Connection, process_id: int, group_id: int | None) -> None:
    await _get_process_raw(conn, process_id)
    await conn.execute(
        "UPDATE zd_processes SET ticket_group_id = $2, updated_at = NOW() WHERE id = $1",
        process_id, group_id,
    )
