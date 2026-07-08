import asyncpg
import json
from app.database.query import fetch_row, execute, fetch
from app.rbac.schemas import RoleCreate, RoleResponse, PermissionAssignRequest, UserRoleAssignRequest
from core.exceptions import NotFoundError, ErrorCodes, ConflictError


async def get_all_roles(conn: asyncpg.Connection) -> list[dict]:
    """Returns all roles as a dictionary and their attached permissions as a list."""
    
    query = """
        SELECT r.id, r.name, r.description, r.created_at,
        COALESCE(json_agg(p.codename) FILTER (WHERE (p.id IS NOT NULL)), '[]') AS permissions
        FROM roles r
        LEFT JOIN role_permissions rp ON rp.role_id = r.id
        LEFT JOIN permissions p ON p.id = rp.permission_id
        GROUP BY r.id
        ORDER BY r.id
    """
    records = await fetch(conn, query, label="rbac:get_all_roles")
    results = []
    
    for row in records:
        data = dict(row)
        if isinstance(data.get("permissions"), str):
            data["permissions"] = json.loads(data["permissions"])
        results.append(data)
        
    return results
    
async def get_role_by_id(conn: asyncpg.Connection, role_id: int) -> dict | None:
    """Returns a role by its id as a dictionary and its attached permissions as a list."""
    query = """
        SELECT r.id, r.name, r.description, r.created_at,
        COALESCE(json_agg(p.codename) FILTER (WHERE (p.id IS NOT NULL)), '[]') AS permissions
        FROM roles r
        LEFT JOIN role_permissions rp ON rp.role_id = r.id
        LEFT JOIN permissions p ON p.id = rp.permission_id
        WHERE r.id = $1
        GROUP BY r.id
        LIMIT 1
    """
    
    row = await fetch_row(conn, query, role_id, label="rbac:get_role_by_id")
    
    if not row:
        raise NotFoundError(message="Role not found", code=ErrorCodes.ROLE_NOT_FOUND)
    
    data = dict(row)
    if isinstance(data.get("permissions"), str):
        data["permissions"] = json.loads(data["permissions"])
    return data

async def get_all_permissions(conn: asyncpg.Connection) -> list[dict]:
    """Returns all permissions as a dictionary."""
    query = """
        SELECT id, codename, description
        FROM permissions
        ORDER BY codename
    """
    
    records = await fetch(conn, query, label="rbac:get_all_permissions")
    
    return [dict(row) for row in records]

async def create_role(conn: asyncpg.Connection, name: str, description: str | None) -> dict:
    """Creates a new role and returns it as a dictionary."""
    query = """
        INSERT INTO roles (name, description) VALUES ($1, $2)
        RETURNING id, name, description, created_at
    """
    try:
        row = await fetch_row(conn, query, name, description, label="rbac:create_role")
        return dict(row)
    except asyncpg.UniqueViolationError:
        raise ConflictError(message="Role already exists", code=ErrorCodes.ROLE_ALREADY_EXISTS)
    
    
async def update_role(conn: asyncpg.Connection, role_id: int, **kwargs):
    """Updates a role and returns it as a dictionary."""
    if not kwargs:
        return await get_role_by_id(conn, role_id)
    
    sets, params = [], [role_id]
    
    for key, value in kwargs.items():
        params.append(value)
        sets.append(f"{key} = ${len(params)}")
    
    sets.append(f"updated_at = NOW()")
    
    sql_query = f"UPDATE roles SET {', '.join(sets)} WHERE id = $1 RETURNING id, name, description, created_at"
    
    try:
        row = await fetch_row(conn, sql_query, *params, label="rbac:update_role")
        return dict(row)
    except asyncpg.UniqueViolationError:
        raise ConflictError(message="Role with that name already exists", code=ErrorCodes.ROLE_ALREADY_EXISTS)
    

async def assign_permissions_to_role(conn: asyncpg.Connection, permission_id: int, role_id: int):
    """Assigns a permission to a role."""
    query = """
        INSERT INTO role_permissions (role_id, permission_id)
        VALUES ($1, $2)
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """
    await execute(conn, query, role_id, permission_id, label="rbac:assign_permissions_to_role")
    
    
async def remove_permission_from_role(conn: asyncpg.Connection, permission_id: int, role_id: int):
    """Removes a permission from a role."""
    query = """
        DELETE FROM role_permissions
        WHERE permission_id = $1 AND role_id = $2
    """
    result = await execute(conn, query, permission_id, role_id, label="rbac:remove_permission_from_role")
    
    return result == "DELETE 1"
    

async def assign_role_to_user(conn: asyncpg.Connection, user_id: int, role_id: int, assigned_by: int):
    """Assigns a user to a role."""
    query = """
        INSERT INTO user_roles (user_id, role_id, assigned_by)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, role_id) DO NOTHING
    """
    await execute(conn, query, user_id, role_id, assigned_by, label="rbac:assign_user_to_role")
    
    
async def remove_role_from_user(conn: asyncpg.Connection, user_id: int, role_id: int):
    """Removes a role from a user."""
    query = """
        DELETE FROM user_roles
        WHERE user_id = $1 AND role_id = $2
    """
    result = await execute(conn, query, user_id, role_id, label="rbac:remove_role_from_user")
    
    return result == "DELETE 1"
