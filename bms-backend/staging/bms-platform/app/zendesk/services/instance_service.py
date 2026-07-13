import asyncpg
import json

from app.zendesk.repository import get_instance_credentials
from app.zendesk.services.zendesk_client import ZendeskClient
from app.zendesk.crypto import decrypt_token
from app.database.query import execute


async def refresh_fields(conn: asyncpg.Connection, instance_id: int, client: ZendeskClient):
    """Refreshes the ticket fields for a given Zendesk instance."""
    fields = await client.get_ticket_fields()
    
    # 3. Delete the existing cache
    await execute(conn, "DELETE FROM zendesk_fields WHERE zendesk_instance_id = $1", instance_id)
    
    # 4. Insert new cache
    for field in fields:
        if not field.get("active", False):
            continue
        
        await execute(
            conn,
            "INSERT INTO zendesk_fields (zendesk_instance_id, zendesk_field_id, title, type, active, raw_data) VALUES ($1, $2, $3, $4, $5, $6)",
            instance_id,
            field["id"],
            field["title"],
            field.get("type"),
            field.get("active", True),
            json.dumps(field),
        )
        
        
async def refresh_forms(conn: asyncpg.Connection, instance_id: int, client: ZendeskClient):
    """Refreshes the ticket forms for a given Zendesk instance."""
    forms = await client.get_ticket_forms()
    
    # 3. Delete the existing cache
    await execute(conn, "DELETE FROM zendesk_forms WHERE zendesk_instance_id = $1", instance_id)
    
    # 4. Insert new cache
    for form in forms:
        if not form.get("active", False):
            continue
        
        await execute(
            conn,
            "INSERT INTO zendesk_forms (zendesk_instance_id, zendesk_form_id, name, active) VALUES ($1, $2, $3, $4)",
            instance_id,
            form["id"],
            form["name"],
            form.get("active", True),
        )
        
        
async def refresh_groups(conn: asyncpg.Connection, instance_id: int, client: ZendeskClient):
    """Refreshes the groups for a given Zendesk instance."""
    groups = await client.get_groups()
    
    # 3. Delete the existing cache
    await execute(conn, "DELETE FROM zendesk_groups WHERE zendesk_instance_id = $1", instance_id)
    
    # 4. Insert new cache
    for group in groups:
        await execute(
            conn,
            "INSERT INTO zendesk_groups (zendesk_instance_id, zendesk_group_id, name) VALUES ($1, $2, $3)",
            instance_id,
            group["id"],
            group["name"],
        )
        
        
async def _build_client(conn: asyncpg.Connection, instance_id: int) -> ZendeskClient:
    """Loads instance credentials and builds a ready-to-use ZendeskClient."""
    creds = await get_instance_credentials(conn, instance_id)
    api_token = decrypt_token(creds["encrypted_api_token"])
    return ZendeskClient(creds["subdomain"], creds["email"], api_token)


async def refresh_all(conn: asyncpg.Connection, instance_id: int):
    """Refreshes all metadata (fields + forms + groups) for a given Zendesk instance."""
    client = await _build_client(conn, instance_id)
    await refresh_fields(conn, instance_id, client)
    await refresh_forms(conn, instance_id, client)
    await refresh_groups(conn, instance_id, client)


async def refresh_fields_only(conn: asyncpg.Connection, instance_id: int):
    """Refreshes just the ticket fields for a given Zendesk instance."""
    client = await _build_client(conn, instance_id)
    await refresh_fields(conn, instance_id, client)


async def refresh_forms_only(conn: asyncpg.Connection, instance_id: int):
    """Refreshes just the ticket forms for a given Zendesk instance."""
    client = await _build_client(conn, instance_id)
    await refresh_forms(conn, instance_id, client)


async def refresh_groups_only(conn: asyncpg.Connection, instance_id: int):
    """Refreshes just the groups for a given Zendesk instance."""
    client = await _build_client(conn, instance_id)
    await refresh_groups(conn, instance_id, client)