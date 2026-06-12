import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
from jose import JWTError, jwt
from passlib.context import CryptContext
from redis.asyncio import Redis

from app.config import get_settings
from app.database.query import fetch_row
from core.exceptions import ErrorCodes, UnauthorizedError

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


# ── password helpers ──────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _make_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _make_token(
        user_id,
        ACCESS_TOKEN_TYPE,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> str:
    return _make_token(
        user_id,
        REFRESH_TOKEN_TYPE,
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise UnauthorizedError("Invalid or expired token", ErrorCodes.TOKEN_INVALID)


# ── Redis refresh-token store ─────────────────────────────────────────────────

def _refresh_key(jti: str) -> str:
    return f"refresh_token:{jti}"


async def store_refresh_token(redis: Redis, jti: str, user_id: int) -> None:
    ttl = settings.refresh_token_expire_days * 86_400
    await redis.setex(_refresh_key(jti), ttl, str(user_id))


async def revoke_refresh_token(redis: Redis, jti: str) -> None:
    await redis.delete(_refresh_key(jti))


async def is_refresh_token_valid(redis: Redis, jti: str) -> bool:
    return await redis.exists(_refresh_key(jti)) == 1


# ── auth flows ────────────────────────────────────────────────────────────────

async def authenticate_user(conn: asyncpg.Connection, email: str, password: str) -> dict:
    row = await fetch_row(
        conn,
        "SELECT id, email, full_name, password_hash, is_active FROM users WHERE email = $1",
        email,
        label="auth:login",
    )
    if not row or not verify_password(password, row["password_hash"]):
        raise UnauthorizedError("Invalid email or password", ErrorCodes.INVALID_CREDENTIALS)
    if not row["is_active"]:
        raise UnauthorizedError("Account is disabled", ErrorCodes.INVALID_CREDENTIALS)
    return dict(row)


async def get_user_by_id(conn: asyncpg.Connection, user_id: int) -> dict | None:
    row = await fetch_row(
        conn,
        "SELECT id, email, full_name, is_active FROM users WHERE id = $1",
        user_id,
        label="auth:get_user",
    )
    return dict(row) if row else None
