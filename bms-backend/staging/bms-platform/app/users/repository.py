import asyncpg
from app.database.query import fetchval, fetch, fetch_row, execute
from core.exceptions import NotFoundError, ConflictError, ErrorCodes


async def get_all_users(conn: asyncpg.Connection, limit: int, offset: int) -> tuple[list[dict], int]:
    """Returns all users as a list of dictionaries."""
    
    total = await fetchval(conn, """
            SELECT COUNT(*) AS total FROM users
        """, label="users:count")
    
    query = """
        SELECT id, email, full_name, is_active, last_login_at, created_at
        FROM users
        ORDER BY created_at DESC
        LIMIT $1
        OFFSET $2
    """
    
    records = await fetch(conn, query, limit, offset, label="users:get_all_users")
    
    if not records:
        return [], 0
    
    return [dict(row) for row in records], total

async def get_user_by_id(conn: asyncpg.Connection, user_id: int) -> dict:
    """Returns a user by their ID, raise NotFoundError if missing."""
    query = """
        SELECT id, email, full_name, is_active, last_login_at, created_at
        FROM users
        WHERE id = $1
    """
    row = await fetch_row(conn, query, user_id, label="users:get_user_by_id")
    
    if not row:
        raise NotFoundError(message="User not found", code=ErrorCodes.USER_NOT_FOUND)
    
    return dict(row)

async def create_user(conn: asyncpg.Connection, email: str, password_hash: str, full_name: str | None = None) -> dict:
    """Creates a new user with a hashed password, raise ConflictError if user already exists."""
    query = """
        INSERT INTO users (email, password_hash, full_name)
        VALUES ($1, $2, $3)
        RETURNING id, email, full_name, is_active, last_login_at, created_at
    """
    try:
        row = await fetch_row(conn, query, email, password_hash, full_name, label="users:create_user")
    except asyncpg.UniqueViolationError:
        raise ConflictError(message="User already exists", code=ErrorCodes.USER_EMAIL_ALREADY_EXISTS)
    
    return dict(row)

async def update_user(conn: asyncpg.Connection, user_id: int, **fields) -> dict:
    """Updates a user's information, raise ConflictError if user email already exists."""
    
    if not fields:
        return await get_user_by_id(conn, user_id)
    
    sets, params = [], [user_id]
    
    for key, value in fields.items():
        params.append(value)
        sets.append(f"{key} = ${len(params)}")
    
    sets.append(f"updated_at = NOW()")
    
    query = f"UPDATE users SET {', '.join(sets)} WHERE id = $1 RETURNING id, email, full_name, is_active, last_login_at, created_at"
    try:
        row = await fetch_row(conn, query, *params, label="users:update_user")
        return dict(row)
    except asyncpg.UniqueViolationError:
        raise ConflictError(message="User with that email already exists", code=ErrorCodes.USER_EMAIL_ALREADY_EXISTS)
    
async def delete_user(conn: asyncpg.Connection, user_id: int) -> bool:
    """Deletes a user, returns True if deleted, False if not found."""
    query = """
        DELETE FROM users WHERE id = $1
    """
    result = await execute(conn, query, user_id, label="users:delete_user")
    
    return result == "DELETE 1"

# adding soft delete user functionality
async def soft_delete_user(conn: asyncpg.Connection, user_id: int) -> None:
    """Soft deletes a user, returns True if deleted, False if not found."""
    query = """
        UPDATE users SET is_active = FALSE, updated_at = NOW() WHERE id = $1
    """
    result = await execute(conn, query, user_id, label="users:soft_delete_user")
    
    if result == "UPDATE 0":
        raise NotFoundError(message="User not found", code=ErrorCodes.USER_NOT_FOUND)
