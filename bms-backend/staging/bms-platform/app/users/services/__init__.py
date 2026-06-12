import asyncpg

from app.auth.services import hash_password
from app.database.query import execute, fetch, fetch_row
from core.exceptions import ConflictError, ErrorCodes, NotFoundError


async def list_users(conn: asyncpg.Connection, skip: int = 0, limit: int = 50) -> dict:
    total = await conn.fetchval("SELECT COUNT(*) FROM users")
    rows = await fetch(
        conn,
        "SELECT id, email, full_name, is_active, last_login_at, created_at FROM users ORDER BY id DESC LIMIT $1 OFFSET $2",
        limit, skip,
        label="users:list",
    )
    return {"total": total, "items": [dict(r) for r in rows]}


async def get_user(conn: asyncpg.Connection, user_id: int) -> dict:
    row = await fetch_row(
        conn,
        "SELECT id, email, full_name, is_active, last_login_at, created_at FROM users WHERE id = $1",
        user_id,
        label="users:get",
    )
    if not row:
        raise NotFoundError("User not found", ErrorCodes.USER_NOT_FOUND)
    return dict(row)


async def create_user(conn: asyncpg.Connection, email: str, password: str, full_name: str | None) -> dict:
    existing = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
    if existing:
        raise ConflictError("Email already registered", ErrorCodes.USER_EMAIL_ALREADY_EXISTS)

    row = await conn.fetchrow(
        """
        INSERT INTO users (email, password_hash, full_name)
        VALUES ($1, $2, $3)
        RETURNING id, email, full_name, is_active, last_login_at, created_at
        """,
        email,
        hash_password(password),
        full_name,
    )
    return dict(row)


async def update_user(conn: asyncpg.Connection, user_id: int, full_name: str | None, is_active: bool | None) -> dict:
    await get_user(conn, user_id)  # raises 404 if missing

    sets, params = [], [user_id]
    if full_name is not None:
        params.append(full_name)
        sets.append(f"full_name = ${len(params)}")
    if is_active is not None:
        params.append(is_active)
        sets.append(f"is_active = ${len(params)}")

    if not sets:
        return await get_user(conn, user_id)

    sets.append("updated_at = NOW()")
    sql = f"UPDATE users SET {', '.join(sets)} WHERE id = $1 RETURNING id, email, full_name, is_active, last_login_at, created_at"
    row = await conn.fetchrow(sql, *params)
    return dict(row)


async def delete_user(conn: asyncpg.Connection, user_id: int) -> None:
    await get_user(conn, user_id)
    await execute(conn, "DELETE FROM users WHERE id = $1", user_id, label="users:delete")


async def get_user_roles(conn: asyncpg.Connection, user_id: int) -> list[dict]:
    await get_user(conn, user_id)
    rows = await fetch(
        conn,
        """
        SELECT r.id, r.name, r.description, ur.assigned_at
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
        WHERE ur.user_id = $1
        ORDER BY r.name
        """,
        user_id,
        label="users:roles",
    )
    return [dict(r) for r in rows]
