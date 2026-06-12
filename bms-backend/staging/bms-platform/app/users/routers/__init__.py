from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_current_user, require_permission
from app.users.models import UserCreate, UserListOut, UserOut, UserUpdate
from app.users.services import (
    create_user,
    delete_user,
    get_user,
    get_user_roles,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListOut, dependencies=[Depends(require_permission("users:read"))])
async def list_users_endpoint(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    async with request.app.state.pool.acquire() as conn:
        return await list_users(conn, skip=skip, limit=limit)


@router.post("", response_model=UserOut, status_code=201, dependencies=[Depends(require_permission("users:write"))])
async def create_user_endpoint(body: UserCreate, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await create_user(conn, body.email, body.password, body.full_name)


@router.get("/me", response_model=UserOut)
async def get_me(request: Request, current_user: dict = Depends(get_current_user)):
    async with request.app.state.pool.acquire() as conn:
        return await get_user(conn, current_user["id"])


@router.get("/{user_id}", response_model=UserOut, dependencies=[Depends(require_permission("users:read"))])
async def get_user_endpoint(user_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await get_user(conn, user_id)


@router.patch("/{user_id}", response_model=UserOut, dependencies=[Depends(require_permission("users:write"))])
async def update_user_endpoint(user_id: int, body: UserUpdate, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await update_user(conn, user_id, body.full_name, body.is_active)


@router.delete("/{user_id}", status_code=204, dependencies=[Depends(require_permission("users:delete"))])
async def delete_user_endpoint(user_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await delete_user(conn, user_id)


@router.get("/{user_id}/roles", dependencies=[Depends(require_permission("users:read"))])
async def get_user_roles_endpoint(user_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await get_user_roles(conn, user_id)
