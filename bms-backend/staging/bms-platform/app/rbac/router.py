import asyncpg
from app.rbac.schemas import RoleCreate, RoleUpdate, PermissionAssignRequest, UserRoleAssignRequest, RoleResponse
from app.rbac import repository as rbac_rep
from app.dependencies import get_pool, get_current_user, require_permission
from core.exceptions import NotFoundError, ErrorCodes, ConflictError
from fastapi import APIRouter, Depends, status, Request
from fastapi.responses import Response

router = APIRouter(
    prefix="/rbac",
)

################### GET ENDPOINTS ###################

@router.get("/permissions", status_code=status.HTTP_200_OK)
async def get_permissions_list(pool: asyncpg.Pool = Depends(get_pool), _: dict = Depends(require_permission("rbac:admin"))) -> list[dict]:
    """Endpoint returning all created permissions"""
    async with pool.acquire() as conn:
        permissions = await rbac_rep.get_all_permissions(conn)
        
    return permissions

@router.get("/roles", status_code=status.HTTP_200_OK, response_model=list[RoleResponse])
async def get_roles(pool: asyncpg.Pool = Depends(get_pool), _: dict = Depends(require_permission("rbac:admin"))) -> list[RoleResponse]:
    """Endpoint returning all created roles"""
    async with pool.acquire() as conn:
        roles = await rbac_rep.get_all_roles(conn)
        
    return roles

@router.get("/roles/{role_id}", status_code=status.HTTP_200_OK, response_model=RoleResponse)
async def get_role_by_id(
    role_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("rbac:admin")), 
    ) -> RoleResponse:
    """Endpoint returning a role by its id"""
    async with pool.acquire() as conn:
        return await rbac_rep.get_role_by_id(conn, role_id)

################### POST ENDPOINTS ###################

@router.post("/roles", status_code=status.HTTP_201_CREATED, response_model=RoleResponse)
async def create_role(
    body: RoleCreate,
    pool: asyncpg.Pool = Depends(get_pool), 
    _: dict = Depends(require_permission("rbac:admin"))) -> dict:
    """Endpoint creating a new role"""
    async with pool.acquire() as conn:
        return await rbac_rep.create_role(conn, body.name, body.description)

@router.post("/users/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def assign_role_to_user(
    user_id: int,
    body: UserRoleAssignRequest, 
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(require_permission("rbac:admin")), 
    ):
    """Endpoint assigning roles to a user"""
    async with pool.acquire() as conn:
        await rbac_rep.assign_role_to_user(conn, user_id, body.role_id, current_user["id"])
        

@router.post("/roles/{role_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
async def assign_permissions_to_role(
    role_id: int,
    body: PermissionAssignRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("rbac:admin")),
    
):
    """Endpoint assigning permissions to a role"""
    async with pool.acquire() as conn:
        await rbac_rep.assign_permissions_to_role(conn, body.permission_id, role_id)

################### PATCH ENDPOINTS ###################

@router.patch("/roles/{role_id}", status_code=status.HTTP_200_OK, response_model=RoleResponse)
async def update_role(
    role_id: int,
    body: RoleUpdate,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("rbac:admin"))
):
    """Endpoint updating a role, raise ConflictError if role name already exists."""
    update_data = body.model_dump(exclude_unset=True)
    async with pool.acquire() as conn:
        return await rbac_rep.update_role(conn, role_id, **update_data)

################### DELETE ENDPOINTS ###################

@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("rbac:admin"))
):
    """Endpoint removing a role from a user"""
    async with pool.acquire() as conn:
        deleted = await rbac_rep.remove_role_from_user(conn, user_id, role_id)
    if not deleted:
        raise NotFoundError(message="Role assignment not found", code=ErrorCodes.ROLE_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("rbac:admin"))
):
    """Endpoint removing a permission from a role"""
    async with pool.acquire() as conn:
        deleted = await rbac_rep.remove_permission_from_role(conn, permission_id, role_id)
    if not deleted:
        raise NotFoundError(message="Permission not found", code=ErrorCodes.PERMISSION_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

