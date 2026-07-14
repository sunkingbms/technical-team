import asyncpg
import jwt

from fastapi import Request
from fastapi import Depends
from redis.asyncio import Redis

from app.config import get_settings
from app.database.query import fetch_row
from core.exceptions import UnauthorizedError, ForbiddenError, ErrorCodes

# The below function ensures that the database pool is available for the request lifespan
# In other way it retrieves database connection stored inside FastAPI application instance
async def get_pool(request: Request) -> asyncpg.Pool:
    """Dependency to get the database pool"""
    return request.app.state.pool

async def get_redis(request: Request) -> Redis:
    """Dependency to get the Redis instance"""
    return request.app.state.redis

async def get_current_user(request: Request, pool: asyncpg.Pool = Depends(get_pool)):
    """Dependency to get the current user"""
    settings = get_settings()
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.removeprefix('Bearer ').strip()
    
    if not token:
        raise UnauthorizedError(message="Missing authorization token", code=ErrorCodes.TOKEN_NOT_FOUND)
    
    try:
        payload = jwt.decode(
            token, 
            settings.secret_key.get_secret_value(), 
            algorithms=[settings.algorithm]
        )
        
        # Checking token type to ensure user has passed the right token
        if payload.get('type') != 'access':
            raise UnauthorizedError(message="Invalid token type", code=ErrorCodes.TOKEN_INVALID)
        
        sub = payload.get('sub')
        
        if not sub:
            raise UnauthorizedError(message="Invalid token", code=ErrorCodes.TOKEN_INVALID)
        
        user_id = int(sub)
        
    except jwt.InvalidTokenError:
        raise UnauthorizedError(message="Invalid token", code=ErrorCodes.TOKEN_INVALID)
    
    async with pool.acquire() as conn:
        query = "SELECT id, email, is_active FROM users WHERE id = $1"
        args = (user_id, )
        user = await fetch_row(conn, query, *args, label="get_current_user")
        
        if not user or not user["is_active"]:
            raise UnauthorizedError(message="User not found or inactive", code=ErrorCodes.USER_NOT_FOUND)
        
    user_data = {
        'id': user['id'],
        'email': user['email'],
        'is_active': user['is_active']
    }
    request.state.user = user_data
    
    return user_data
    
def require_permission(permission: str):
    async def _check(request: Request, pool: asyncpg.Pool = Depends(get_pool)) -> dict:
        user = await get_current_user(request, pool)
        
        async with pool.acquire() as conn:
            row = await fetch_row(
                conn,
                """
                SELECT 1 FROM user_roles ur
                JOIN role_permissions rp ON rp.role_id = ur.role_id
                JOIN permissions p ON p.id = rp.permission_id
                WHERE ur.user_id = $1 AND p.codename = $2
                LIMIT 1
                """,
                user["id"], permission,
                label="check_permission",
            )
        
        if not row:
            raise ForbiddenError(message=f"Required permission: '{permission}'", code=ErrorCodes.PERMISSION_DENIED)
        
        return user
    return _check