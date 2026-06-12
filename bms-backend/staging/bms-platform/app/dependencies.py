from fastapi import Request, Depends
from fastapi.security import HTTPBearer
import asyncpg

_bearer = HTTPBearer(auto_error=False)


async def get_pool(request: Request) -> asyncpg.Pool:
    """Dependency to get the database pool"""
    return request.app.state.pool


async def get_redis(request: Request):
    """Dependency to get the Redis client"""
    return request.app.state.redis


async def get_current_user(
    request: Request,
    credentials=Depends(_bearer),
) -> dict:
    from app.auth.services import decode_token, get_user_by_id
    from core.exceptions import ErrorCodes, UnauthorizedError

    if not credentials:
        raise UnauthorizedError("Authentication required", ErrorCodes.TOKEN_NOT_FOUND)

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type", ErrorCodes.TOKEN_INVALID)

    user_id = int(payload["sub"])
    async with request.app.state.pool.acquire() as conn:
        user = await get_user_by_id(conn, user_id)

    if not user:
        raise UnauthorizedError("User not found", ErrorCodes.USER_NOT_FOUND)
    if not user["is_active"]:
        raise UnauthorizedError("Account is disabled", ErrorCodes.INVALID_CREDENTIALS)

    return user


def require_permission(permission: str):
    """
    Inject as a route dependency:
        dependencies=[Depends(require_permission("zendesk:create"))]
    """
    async def _check(
        request: Request,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        from core.exceptions import ErrorCodes, ForbiddenError
        async with request.app.state.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1 FROM user_roles ur
                JOIN role_permissions rp ON rp.role_id = ur.role_id
                JOIN permissions p      ON p.id = rp.permission_id
                WHERE ur.user_id = $1 AND p.codename = $2
                LIMIT 1
                """,
                current_user["id"],
                permission,
            )
        if not row:
            raise ForbiddenError(
                f"Permission '{permission}' required",
                ErrorCodes.PERMISSION_DENIED,
            )
        return current_user

    return _check
