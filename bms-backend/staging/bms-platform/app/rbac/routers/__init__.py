from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user, require_permission
from app.rbac.models import AddPermissionRequest, AssignRoleRequest, RoleCreate, RoleOut
from app.rbac.services import (
    add_permission_to_role,
    assign_role_to_user,
    create_role,
    list_permissions,
    list_roles,
    remove_role_from_user,
)

router = APIRouter(prefix="/rbac", tags=["RBAC"])

_admin = [Depends(require_permission("rbac:admin"))]


@router.get("/roles", dependencies=_admin)
async def list_roles_endpoint(request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await list_roles(conn)


@router.post("/roles", response_model=RoleOut, status_code=201, dependencies=_admin)
async def create_role_endpoint(body: RoleCreate, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await create_role(conn, body.name, body.description)


@router.get("/permissions", dependencies=_admin)
async def list_permissions_endpoint(request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await list_permissions(conn)


@router.post("/roles/{role_id}/permissions", status_code=204, dependencies=_admin)
async def add_permission(role_id: int, body: AddPermissionRequest, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await add_permission_to_role(conn, role_id, body.permission_id)


@router.post("/users/{user_id}/roles", status_code=204, dependencies=_admin)
async def assign_role(
    user_id: int,
    body: AssignRoleRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with request.app.state.pool.acquire() as conn:
        await assign_role_to_user(conn, user_id, body.role_id, current_user["id"])


@router.delete("/users/{user_id}/roles/{role_id}", status_code=204, dependencies=_admin)
async def remove_role(user_id: int, role_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await remove_role_from_user(conn, user_id, role_id)
