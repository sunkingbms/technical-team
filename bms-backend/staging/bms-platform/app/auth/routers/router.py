import asyncpg
from fastapi import APIRouter, Depends, status, Request
from redis.asyncio import Redis
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.models.schemas import (
    LoginRequest, 
    TokenResponse, 
    RefreshTokenRequest
)
from app.auth.services.service import (
    decode_token,
    revoke_token,
    rotate_refresh_token,
    create_token,
    authenticate_user
)
from core.exceptions import UnauthorizedError, ErrorCodes
from app.dependencies import get_pool, get_redis, get_current_user
from app.database.query import execute
from app.users import repository as users_rep
from app.users.schemas import UserResponse


router = APIRouter(
    prefix="/auth"
)

limiter = Limiter(key_func=get_remote_address)

@router.post("/login", status_code=status.HTTP_200_OK, response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, redis: Redis = Depends(get_redis), pool: asyncpg.Pool = Depends(get_pool)) -> TokenResponse:
    """Login a user into the system."""
    async with pool.acquire() as conn:
        user = await authenticate_user(conn, body.email, body.password)
        
        await execute(
            conn, 
            "UPDATE users SET last_login_at = NOW() WHERE id =$1", user["id"],
            label="updating_last_login_at"
        )
        
    tokens = await create_token(redis=redis, user_id=user["id"])
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )
    
@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=TokenResponse)
@limiter.limit("20/minute")
async def refresh(request: Request, body: RefreshTokenRequest, redis: Redis = Depends(get_redis)) -> TokenResponse:
    """Method used to refresh an access token using a refresh token."""
    tokens = await rotate_refresh_token(redis, body.refresh_token)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"]
    )
    
@router.get("/me", status_code=status.HTTP_200_OK, response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """Returns the profile of the currently authenticated user (from the access token)."""
    async with pool.acquire() as conn:
        return await users_rep.get_user_by_id(conn, current_user["id"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshTokenRequest, redis: Redis = Depends(get_redis), current_user: dict = Depends(get_current_user) ):
    """Method used to logout a user by revoking their refresh token."""
    
    try:
        payload = decode_token(body.refresh_token)
        if str(current_user["id"]) != payload.get("sub"):
            raise UnauthorizedError(message="Invalid token", code=ErrorCodes.TOKEN_INVALID)
    except UnauthorizedError:
        raise
    except Exception:
        pass
    
    await revoke_token(redis=redis, refresh_token=body.refresh_token)
    
    return None
    