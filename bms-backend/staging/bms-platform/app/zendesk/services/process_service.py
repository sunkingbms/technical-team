"""
Process business logic: CRUD passthrough plus the combined field / tag /
form / group configuration view used by the process config UI.
"""
import json

import asyncpg

from app.zendesk import process_repository as repo


def _parse_json_col(val):
    """Return val as a Python object; handles str (no JSONB codec) or already-parsed."""
    if val is None:
        return []
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return []
    return val  # already a list/dict via the asyncpg JSONB codec


async def list_processes(conn: asyncpg.Connection, instance_id: int) -> list[dict]:
    return await repo.list_processes(conn, instance_id)


async def get_process(conn: asyncpg.Connection, process_id: int) -> dict:
    return await repo.get_process(conn, process_id)


async def create_process(conn: asyncpg.Connection, instance_id: int, data: dict, created_by: int) -> dict:
    return await repo.create_process(conn, instance_id, data, created_by)


async def update_process(conn: asyncpg.Connection, process_id: int, data: dict) -> dict:
    return await repo.update_process(conn, process_id, data)


async def delete_process(conn: asyncpg.Connection, process_id: int) -> None:
    await repo.delete_process(conn, process_id)


async def get_process_fields(conn: asyncpg.Connection, process_id: int) -> dict:
    """Returns configured fields + process form/group/tags for the config UI."""
    process = await repo.get_process(conn, process_id)
    fields = await repo.get_process_fields(conn, process_id)
    tags = await repo.get_process_tags(conn, process_id)
    forms = await repo.get_instance_forms(conn, process["zendesk_instance_id"])
    groups = await repo.get_instance_groups(conn, process["zendesk_instance_id"])

    parsed_fields = []
    for f in fields:
        row = dict(f)
        raw_data = _parse_json_col(row.pop("raw_data", None))
        raw_data = raw_data if isinstance(raw_data, dict) else {}
        row["custom_field_options"] = raw_data.get("custom_field_options") or []
        row["system_field_options"] = raw_data.get("system_field_options") or []
        parsed_fields.append(row)

    return {
        "fields": parsed_fields,
        "tags": tags or [],
        "ticket_form_id": process.get("ticket_form_id"),
        "ticket_group_id": process.get("ticket_group_id"),
        "available_forms": forms,
        "available_groups": groups,
    }


async def get_available_fields(conn: asyncpg.Connection, process_id: int) -> list[dict]:
    rows = await repo.get_available_fields(conn, process_id)
    out = []
    for r in rows:
        row = dict(r)
        raw_data = _parse_json_col(row.pop("raw_data", None))
        raw_data = raw_data if isinstance(raw_data, dict) else {}
        row["custom_field_options"] = raw_data.get("custom_field_options") or []
        out.append(row)
    return out


async def add_field_to_process(conn: asyncpg.Connection, process_id: int, field_id: int) -> None:
    await repo.add_field_to_process(conn, process_id, field_id)


async def update_process_field(
    conn: asyncpg.Connection, process_id: int, field_id: int, default_value, user_visible
) -> None:
    await repo.update_process_field(conn, process_id, field_id, default_value, user_visible)


async def remove_field_from_process(conn: asyncpg.Connection, process_id: int, field_id: int) -> None:
    await repo.remove_field_from_process(conn, process_id, field_id)


async def save_tags(conn: asyncpg.Connection, process_id: int, tags: list[str]) -> None:
    await repo.save_tags(conn, process_id, tags)


async def set_ticket_form(conn: asyncpg.Connection, process_id: int, form_id: int | None) -> None:
    await repo.set_ticket_form(conn, process_id, form_id)


async def set_ticket_group(conn: asyncpg.Connection, process_id: int, group_id: int | None) -> None:
    await repo.set_ticket_group(conn, process_id, group_id)
