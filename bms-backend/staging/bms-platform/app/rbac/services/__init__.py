import asyncpg

from app.database.query import fetch, fetch_row
from core.exceptions import ConflictError, ErrorCodes, NotFoundError


async def list_roles(conn: asyncpg.Connection) -> list[dict]:
    rows = await fetch(
        conn,
        """
        SELECT r.id, r.name, r.description, r.created_at,
               COALESCE(json_agg(p.codename) FILTER (WHERE p.id IS NOT NULL), '[]') AS permissions
        FROM roles r
        LEFT JOIN role_permissions rp ON rp.role_id = r.id
        LEFT JOIN permissions p ON p.id = rp.permission_id
        GROUP BY r.id
        ORDER BY r.name
        """,
        label="rbac:list_roles",
    )
    return [dict(r) for r in rows]


async def create_role(conn: asyncpg.Connection, name: str, description: str | None) -> dict:
    existing = await conn.fetchval("SELECT id FROM roles WHERE name = $1", name)
    if existing:
        raise ConflictError(f"Role '{name}' already exists", ErrorCodes.ROLE_ALREADY_EXISTS)

    row = await conn.fetchrow(
        "INSERT INTO roles (name, description) VALUES ($1, $2) RETURNING id, name, description, created_at",
        name, description,
    )
    return dict(row)


async def get_role(conn: asyncpg.Connection, role_id: int) -> dict:
    row = await fetch_row(
        conn,
        "SELECT id, name, description, created_at FROM roles WHERE id = $1",
        role_id,
        label="rbac:get_role",
    )
    if not row:
        raise NotFoundError("Role not found", ErrorCodes.ROLE_NOT_FOUND)
    return dict(row)


async def add_permission_to_role(conn: asyncpg.Connection, role_id: int, permission_id: int) -> None:
    await get_role(conn, role_id)
    perm = await conn.fetchval("SELECT id FROM permissions WHERE id = $1", permission_id)
    if not perm:
        raise NotFoundError("Permission not found", ErrorCodes.ROLE_NOT_FOUND)

    await conn.execute(
        "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        role_id, permission_id,
    )


async def list_permissions(conn: asyncpg.Connection) -> list[dict]:
    rows = await fetch(conn, "SELECT id, codename, description FROM permissions ORDER BY codename", label="rbac:permissions")
    return [dict(r) for r in rows]


async def assign_role_to_user(conn: asyncpg.Connection, user_id: int, role_id: int, assigned_by: int) -> None:
    await get_role(conn, role_id)
    user = await conn.fetchval("SELECT id FROM users WHERE id = $1", user_id)
    if not user:
        raise NotFoundError("User not found", ErrorCodes.USER_NOT_FOUND)

    await conn.execute(
        "INSERT INTO user_roles (user_id, role_id, assigned_by) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
        user_id, role_id, assigned_by,
    )


async def remove_role_from_user(conn: asyncpg.Connection, user_id: int, role_id: int) -> None:
    await conn.execute(
        "DELETE FROM user_roles WHERE user_id = $1 AND role_id = $2",
        user_id, role_id,
    )
