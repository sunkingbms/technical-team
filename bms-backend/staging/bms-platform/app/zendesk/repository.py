import asyncpg

from app.database.query import fetch, fetch_row, execute, fetchval
from core.exceptions import NotFoundError, ErrorCodes, ConflictError



async def get_all_instances(conn: asyncpg.Connection) -> list[dict]:
    """Get all create instances or raise NotFoundError if none found."""
    query = """
         SELECT id, name, subdomain, email, is_deleted, created_at, updated_at
         FROM zendesk_instances
         WHERE is_deleted = FALSE
         ORDER BY name ASC
    """
    
    results = await fetch(conn, query, label="zendesk:get_all_instances")
    
    return [dict(row) for row in results]


async def get_instance_by_id(conn: asyncpg.Connection, instance_id: int) -> dict:
    """Get a single instance by ID or raise NotFoundError if missing."""
    query = """
        SELECT id, name, subdomain, email, is_deleted, created_at, updated_at
        FROM zendesk_instances
        WHERE id = $1 AND is_deleted = FALSE
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
        RETURNING id, name, subdomain, email, is_deleted, created_at, updated_at
    """
    try:
        row = await fetch_row(conn, query, name, subdomain, email, encrypted_api_token, created_by, label="zendesk:create_instance")
    except asyncpg.UniqueViolationError:
        raise ConflictError(message="Zendesk instance already exists", code=ErrorCodes.INSTANCE_ALREADY_EXISTS)
    
    return dict(row)

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
        RETURNING id, name, subdomain, email, is_deleted, created_at, updated_at
    """
    
    try:
        row = await fetch_row(conn, query, *params, label="zendesk:update_instance")
        if not row:
            raise NotFoundError(message="Zendesk instance not found", code=ErrorCodes.INSTANCE_NOT_FOUND)
        return dict(row)
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