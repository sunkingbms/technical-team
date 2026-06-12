from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis

import asyncpg

from app.auth.models import LoginRequest, RefreshRequest, TokenResponse, UserOut
from app.auth.services import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_id,
    is_refresh_token_valid,
    revoke_refresh_token,
    store_refresh_token,
)
from app.dependencies import get_pool, get_current_user, get_redis
from core.exceptions import ErrorCodes, UnauthorizedError

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    pool: asyncpg.Pool = await get_pool(request)
    redis: Redis = await get_redis(request)

    async with pool.acquire() as conn:
        user = await authenticate_user(conn, body.email, body.password)
        await conn.execute(
            "UPDATE users SET last_login_at = NOW() WHERE id = $1", user["id"]
        )

    access_token = create_access_token(user["id"])
    refresh_token = create_refresh_token(user["id"])

    # Store refresh token jti in Redis
    refresh_payload = decode_token(refresh_token)
    await store_refresh_token(redis, refresh_payload["jti"], user["id"])

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request):
    redis: Redis = await get_redis(request)
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid token type", ErrorCodes.TOKEN_INVALID)

    jti = payload["jti"]
    if not await is_refresh_token_valid(redis, jti):
        raise UnauthorizedError("Token has been revoked", ErrorCodes.TOKEN_REVOKED)

    user_id = int(payload["sub"])
    await revoke_refresh_token(redis, jti)  # rotate: revoke old

    new_access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    new_payload = decode_token(new_refresh)
    await store_refresh_token(redis, new_payload["jti"], user_id)

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout", status_code=204)
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    redis: Redis = await get_redis(request)
    # Best-effort: revoke any active refresh tokens (client should also discard)
    # If Bearer token carries jti we revoke it; otherwise no-op
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") == "refresh":
                await revoke_refresh_token(redis, payload["jti"])
        except Exception:
            pass


@router.get("/me", response_model=UserOut)
async def me(request: Request, current_user: dict = Depends(get_current_user)):
    pool: asyncpg.Pool = await get_pool(request)
    async with pool.acquire() as conn:
        user = await get_user_by_id(conn, current_user["id"])
    return UserOut(**user)
