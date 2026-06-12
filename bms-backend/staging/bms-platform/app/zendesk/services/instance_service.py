"""
Instance CRUD and metadata refresh (fields, forms, groups).
"""
import asyncpg

from app.database.query import fetch, fetch_row
from app.zendesk.services.zendesk_client import ZendeskClient
from core.exceptions import ErrorCodes, NotFoundError

# Zendesk field columns we persist (mirrors PHP $allowedColumns)
_FIELD_COLUMNS = {
    "agent_description", "collapsed_for_agents", "created_at", "creator_app_name",
    "creator_user_id", "custom_field_options", "custom_statuses", "description",
    "editable_in_portal", "position", "raw_description", "raw_title",
    "raw_title_in_portal", "regexp_for_validation", "relationship_filter",
    "relationship_target_type", "removable", "required", "required_in_portal",
    "sub_type_id", "system_field_options", "tag", "title", "title_in_portal",
    "type", "updated_at", "url", "visible_in_portal", "key",
    "active",   # used for filtering but also stored
}


async def list_instances(conn: asyncpg.Connection) -> list[dict]:
    rows = await fetch(
        conn,
        """
        SELECT
            i.id, i.instance_name, i.subdomain, i.email, i.created_at,
            (SELECT COUNT(*) FROM zd_processes p WHERE p.instance_id = i.id AND NOT p.is_deleted) AS process_count,
            (SELECT COUNT(*) FROM zd_fields   f WHERE f.zendesk_instance_id = i.id)               AS field_count,
            (SELECT COUNT(*) FROM zd_forms    fm WHERE fm.zendesk_instance_id = i.id)             AS forms_count,
            (SELECT COUNT(*) FROM zd_groups   g WHERE g.zendesk_instance_id = i.id)               AS groups_count
        FROM zd_instances i
        WHERE NOT i.is_deleted
        ORDER BY i.id DESC
        """,
        label="instances:list",
    )
    return [dict(r) for r in rows]


async def get_instance(conn: asyncpg.Connection, instance_id: int) -> dict:
    row = await fetch_row(
        conn,
        """
        SELECT
            i.id, i.instance_name, i.subdomain, i.email, i.created_at,
            (SELECT COUNT(*) FROM zd_processes p WHERE p.instance_id = i.id AND NOT p.is_deleted) AS process_count,
            (SELECT COUNT(*) FROM zd_fields   f WHERE f.zendesk_instance_id = i.id)               AS field_count,
            (SELECT COUNT(*) FROM zd_forms    fm WHERE fm.zendesk_instance_id = i.id)             AS forms_count,
            (SELECT COUNT(*) FROM zd_groups   g WHERE g.zendesk_instance_id = i.id)               AS groups_count
        FROM zd_instances i
        WHERE i.id = $1 AND NOT i.is_deleted
        """,
        instance_id,
        label="instances:get",
    )
    if not row:
        raise NotFoundError("Instance not found", ErrorCodes.INSTANCE_NOT_FOUND)
    return dict(row)


async def get_instance_credentials(conn: asyncpg.Connection, instance_id: int) -> dict:
    """Returns subdomain, email, access_token (for internal use by Celery)."""
    row = await fetch_row(
        conn,
        "SELECT id, subdomain, email, access_token FROM zd_instances WHERE id = $1 AND NOT is_deleted",
        instance_id,
        label="instances:creds",
    )
    if not row:
        raise NotFoundError("Instance not found", ErrorCodes.INSTANCE_NOT_FOUND)
    return dict(row)


async def create_instance(conn: asyncpg.Connection, data: dict, created_by: int) -> dict:
    row = await conn.fetchrow(
        """
        INSERT INTO zd_instances (instance_name, subdomain, email, access_token, created_by)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, instance_name, subdomain, email, created_at
        """,
        data["instance_name"], data["subdomain"], data["email"],
        data["access_token"], created_by,
    )
    return {**dict(row), "process_count": 0, "field_count": 0, "forms_count": 0, "groups_count": 0}


async def update_instance(conn: asyncpg.Connection, instance_id: int, data: dict) -> dict:
    await get_instance(conn, instance_id)
    fields = {k: v for k, v in data.items() if v is not None}
    if not fields:
        return await get_instance(conn, instance_id)

    sets, params = [], [instance_id]
    for col, val in fields.items():
        params.append(val)
        sets.append(f"{col} = ${len(params)}")
    sets.append("updated_at = NOW()")

    await conn.execute(
        f"UPDATE zd_instances SET {', '.join(sets)} WHERE id = $1",
        *params,
    )
    return await get_instance(conn, instance_id)


async def delete_instance(conn: asyncpg.Connection, instance_id: int) -> None:
    await get_instance(conn, instance_id)
    await conn.execute("UPDATE zd_instances SET is_deleted = TRUE WHERE id = $1", instance_id)


# ── metadata refresh ──────────────────────────────────────────────────────────

async def refresh_fields(conn: asyncpg.Connection, instance_id: int) -> dict:
    inst = await get_instance_credentials(conn, instance_id)
    client = ZendeskClient(inst["subdomain"], inst["email"], inst["access_token"])
    fields = await client.get_ticket_fields()

    await conn.execute("DELETE FROM zd_fields WHERE zendesk_instance_id = $1", instance_id)

    active_fields = [f for f in fields if f.get("active", True)]
    for field in active_fields:
        import json
        row_data = {"zendesk_instance_id": instance_id, "zendesk_field_id": field["id"]}
        for key in _FIELD_COLUMNS:
            val = field.get(key)
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            row_data[key] = val

        cols = list(row_data.keys())
        placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
        col_names = ", ".join(cols)
        await conn.execute(
            f"INSERT INTO zd_fields ({col_names}) VALUES ({placeholders})",
            *[row_data[c] for c in cols],
        )

    return {"status": "success", "message": f"{len(active_fields)} fields retrieved successfully."}


async def refresh_forms(conn: asyncpg.Connection, instance_id: int) -> dict:
    inst = await get_instance_credentials(conn, instance_id)
    client = ZendeskClient(inst["subdomain"], inst["email"], inst["access_token"])
    forms = await client.get_ticket_forms()

    await conn.execute("DELETE FROM zd_forms WHERE zendesk_instance_id = $1", instance_id)
    for form in forms:
        await conn.execute(
            "INSERT INTO zd_forms (zendesk_instance_id, form_id, form_name) VALUES ($1, $2, $3)",
            instance_id, form["id"], form.get("name"),
        )
    return {"status": "success", "message": f"{len(forms)} forms retrieved successfully."}


async def refresh_groups(conn: asyncpg.Connection, instance_id: int) -> dict:
    inst = await get_instance_credentials(conn, instance_id)
    client = ZendeskClient(inst["subdomain"], inst["email"], inst["access_token"])
    groups = await client.get_groups()

    await conn.execute("DELETE FROM zd_groups WHERE zendesk_instance_id = $1", instance_id)
    for group in groups:
        await conn.execute(
            "INSERT INTO zd_groups (zendesk_instance_id, group_id, group_name) VALUES ($1, $2, $3)",
            instance_id, group["id"], group.get("name"),
        )
    return {"status": "success", "message": f"{len(groups)} groups retrieved successfully."}
