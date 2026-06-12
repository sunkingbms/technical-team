from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user, require_permission
from app.zendesk.models import (
    InstanceCreate, InstanceOut, InstanceUpdate, RefreshResponse,
)
from app.zendesk.services.instance_service import (
    create_instance, delete_instance, get_instance,
    list_instances, refresh_fields, refresh_forms, refresh_groups, update_instance,
)

router = APIRouter(prefix="/zendesk/instances", tags=["Zendesk — Instances"])

_read  = [Depends(require_permission("zendesk:read"))]
_admin = [Depends(require_permission("zendesk:admin"))]


@router.get("", response_model=list[InstanceOut], dependencies=_read)
async def list_instances_endpoint(request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await list_instances(conn)


@router.post("", response_model=InstanceOut, status_code=201, dependencies=_admin)
async def create_instance_endpoint(
    body: InstanceCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with request.app.state.pool.acquire() as conn:
        return await create_instance(conn, body.model_dump(), current_user["id"])


@router.get("/{instance_id}", response_model=InstanceOut, dependencies=_read)
async def get_instance_endpoint(instance_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await get_instance(conn, instance_id)


@router.patch("/{instance_id}", response_model=InstanceOut, dependencies=_admin)
async def update_instance_endpoint(instance_id: int, body: InstanceUpdate, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await update_instance(conn, instance_id, body.model_dump(exclude_none=True))


@router.delete("/{instance_id}", status_code=204, dependencies=_admin)
async def delete_instance_endpoint(instance_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await delete_instance(conn, instance_id)


@router.post("/{instance_id}/refresh-fields", response_model=RefreshResponse, dependencies=_admin)
async def refresh_fields_endpoint(instance_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await refresh_fields(conn, instance_id)


@router.post("/{instance_id}/refresh-forms", response_model=RefreshResponse, dependencies=_admin)
async def refresh_forms_endpoint(instance_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await refresh_forms(conn, instance_id)


@router.post("/{instance_id}/refresh-groups", response_model=RefreshResponse, dependencies=_admin)
async def refresh_groups_endpoint(instance_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await refresh_groups(conn, instance_id)
