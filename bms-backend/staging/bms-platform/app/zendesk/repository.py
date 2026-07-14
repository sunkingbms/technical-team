import asyncpg

from app.database.query import fetch, fetch_row, execute, fetchval
from core.exceptions import NotFoundError, ErrorCodes, ConflictError



# Aggregate counts are computed as correlated subqueries rather than a JOIN + GROUP BY
# so that an instance with zero rows in one of the four child tables still returns 0
# instead of being silently dropped/duplicated.
_INSTANCE_COUNTS_SELECT = """
        SELECT
            i.id, i.name, i.subdomain, i.email, i.is_deleted, i.created_at, i.updated_at,
            (SELECT COUNT(*) FROM zendesk_processes p WHERE p.zendesk_instance_id = i.id AND NOT p.is_deleted) AS process_count,
            (SELECT COUNT(*) FROM zendesk_fields f    WHERE f.zendesk_instance_id = i.id) AS field_count,
            (SELECT COUNT(*) FROM zendesk_forms fo    WHERE fo.zendesk_instance_id = i.id) AS forms_count,
            (SELECT COUNT(*) FROM zendesk_groups g    WHERE g.zendesk_instance_id = i.id) AS groups_count
        FROM zendesk_instances i
"""


async def get_all_instances(conn: asyncpg.Connection) -> list[dict]:
    """Get all create instances or raise NotFoundError if none found."""
    query = _INSTANCE_COUNTS_SELECT + """
         WHERE i.is_deleted = FALSE
         ORDER BY i.name ASC
    """

    results = await fetch(conn, query, label="zendesk:get_all_instances")

    return [dict(row) for row in results]


async def get_instance_by_id(conn: asyncpg.Connection, instance_id: int) -> dict:
    """Get a single instance by ID or raise NotFoundError if missing."""
    query = _INSTANCE_COUNTS_SELECT + """
        WHERE i.id = $1 AND i.is_deleted = FALSE
    """

    result = await fetch_row(conn, query, instance_id, label="zendesk:get_instance_by_id")

    if not result:
        raise NotFoundError(message="Zendesk instance not found", code=ErrorCodes.INSTANCE_NOT_FOUND)

    return dict(result)


async def get_instance_credentials(conn: asyncpg.Connection, instance_id: int) -> dict:
    """Get the credentials for a single instance or raise NotFoundError if missing."""
    
    query = """
         SELECT subdomain, email, encrypted_api_token
         FROM zendesk_instances
         WHERE id = $1 AND is_deleted = FALSE
    """
    
    result = await fetch_row(conn, query, instance_id, label="zendesk:get_instance_credentials")
    
    if not result:
        raise NotFoundError(message="Zendesk instance credentials not found", code=ErrorCodes.INSTANCE_NOT_FOUND)
    
    return dict(result)

async def create_instance(conn: asyncpg.Connection, name: str, subdomain: str, email: str, encrypted_api_token: str, created_by: int) -> dict:
    """Create a new Zendesk instance."""

    query = """
        INSERT INTO zendesk_instances (name, subdomain, email, encrypted_api_token, created_by)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
    """
    try:
        row = await fetch_row(conn, query, name, subdomain, email, encrypted_api_token, created_by, label="zendesk:create_instance")
    except asyncpg.UniqueViolationError:
        raise ConflictError(message="Zendesk instance already exists", code=ErrorCodes.INSTANCE_ALREADY_EXISTS)

    # Re-fetch through get_instance_by_id so the response includes the same
    # process/field/forms/groups counts as the list/detail endpoints (a brand
    # new instance will just show zeros, which is correct).
    return await get_instance_by_id(conn, row["id"])

async def update_instance(conn: asyncpg.Connection, instance_id: int, **fields) -> dict:
    """Dynamically update a Zendesk instance."""
    if not fields:
        return await get_instance_by_id(conn, instance_id)
    
    sets, params = [], [instance_id]
    
    for key, value in fields.items():
        params.append(value)
        sets.append(f"{key} = ${len(params)}")  
    
    sets.append(f"updated_at = NOW()")

    query = f"""
        UPDATE zendesk_instances
        SET {', '.join(sets)}
        WHERE id = $1 AND is_deleted = FALSE
        RETURNING id
    """

    try:
        row = await fetch_row(conn, query, *params, label="zendesk:update_instance")
        if not row:
            raise NotFoundError(message="Zendesk instance not found", code=ErrorCodes.INSTANCE_NOT_FOUND)
        return await get_instance_by_id(conn, row["id"])
    except asyncpg.UniqueViolationError:
        raise ConflictError(message="Zendesk instance with that subdomain already exists", code=ErrorCodes.INSTANCE_ALREADY_EXISTS)
    
    

async def soft_delete_instance(conn: asyncpg.Connection, instance_id: int) -> None:
    """Delete a Zendesk instance."""
    
    query = """
        UPDATE zendesk_instances
        SET is_deleted = TRUE, updated_at = NOW()
        WHERE id = $1 AND is_deleted = FALSE
    """
    result = await execute(conn, query, instance_id, label="zendesk:soft_delete_instance")
    
    if result == "UPDATE 0":
        raise NotFoundError(message="Zendesk instance not found", code=ErrorCodes.INSTANCE_NOT_FOUND)