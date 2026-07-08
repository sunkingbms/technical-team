import jwt
import uuid
import asyncpg

from datetime import timedelta, datetime, timezone
from redis.asyncio import Redis
from app.config import get_settings
from app.database.query import fetch_row
from app.auth.utils import verify_password, hasher
from core.exceptions import UnauthorizedError, ErrorCodes

DUMMY_PASSWORD = hasher.hash("3cbb274c3f307a9dcd9a3637c8e8f0a037ef38ffa1cb0aca39e95432d6fabf68")

def _make_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    """utility function used to create a JWT token"""
    settings = get_settings()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": datetime.now(timezone.utc),
        "exp": expire
    }
    
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=settings.algorithm)

def decode_token(token: str) -> dict:
    """utility function used to decode a JWT token"""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=[settings.algorithm])
    except jwt.InvalidTokenError:
        raise UnauthorizedError(message="Token invalid or expired", code=ErrorCodes.TOKEN_INVALID)


async def authenticate_user(conn: asyncpg.Connection, email: str, password: str) -> dict:
    """Verifies credentials of a user against the database safely"""
    query = "SELECT id, email, password_hash, is_active from users where email=$1"
    args = (email.lower().strip(), )
    
    user = await fetch_row(conn, query, *args, label="authenticate_user")
    
    if not user:
        verify_password(password, DUMMY_PASSWORD)
        raise UnauthorizedError(message="Invalid credentials", code=ErrorCodes.INVALID_CREDENTIALS)
    
    hash_to_verify = user["password_hash"] or DUMMY_PASSWORD
        
    if not verify_password(password, hash_to_verify):
        raise UnauthorizedError(message="Invalid credentials", code=ErrorCodes.INVALID_CREDENTIALS)
    
    if not user["is_active"]:
        raise UnauthorizedError(message="Invalid credentials", code=ErrorCodes.INVALID_CREDENTIALS)
    
    return dict(user)

async def create_token(redis: Redis, user_id: int) -> dict:
    """Create a new access token and whitelist it in Redis"""
    settings = get_settings()
    access_token = _make_token(user_id, "access", timedelta(minutes=settings.access_token_expire_minutes))
    refresh_token = _make_token(user_id, "refresh", timedelta(days=settings.refresh_token_expire_days))
    
    # extracting JIT from refresh_token
    decoded_refresh = decode_token(refresh_token)
    jti = decoded_refresh.get("jti")
    
    # Save the jit to redis for seven days
    await redis.set(f"refresh_token:{jti}", str(user_id), ex=settings.refresh_token_expire_days * 24 * 60 * 60)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
    
async def rotate_refresh_token(redis: Redis, refresh_token_str: str) -> dict:
    """Rotate a refresh token by generating a new one and updating the Redis cache"""
    decoded_refresh = decode_token(refresh_token_str)
    if decoded_refresh.get("type") != "refresh":
        raise UnauthorizedError(message="Invalid token type", code=ErrorCodes.TOKEN_INVALID)
    
    jti = decoded_refresh.get("jti")
    user_id_str = decoded_refresh.get("sub")
    
    # Checks redis whitelist for jit
    redis_key = f"refresh_token:{jti}"
    stored_user_id = await redis.get(redis_key)
    
    if not stored_user_id or stored_user_id != user_id_str:
        raise UnauthorizedError(message="Invalid token", code=ErrorCodes.TOKEN_INVALID)
    
    # Deleting the old refresh token from redis ensuring that the token is not used again
    await redis.delete(redis_key)
    
    return await create_token(redis, int(user_id_str))

async def revoke_token(redis: Redis, refresh_token_str: str) -> None:
    """Invalidate a user's current access session."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            refresh_token_str,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"verify_exp": False}
        )
        jti = payload.get("jti")
        
        if jti:
            await redis.delete(f"refresh_token:{jti}")
    except jwt.InvalidTokenError:
        pass