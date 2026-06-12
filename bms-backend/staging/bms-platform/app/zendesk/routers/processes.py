from fastapi import APIRouter, Depends, Request

from app.dependencies import get_current_user, require_permission
from app.zendesk.models import (
    AddFieldRequest, ProcessCreate, ProcessOut, ProcessUpdate,
    SetFormRequest, SetGroupRequest, SetTagsRequest, UpdateFieldRequest,
)
from app.zendesk.services.process_service import (
    add_field_to_process, create_process, delete_process,
    get_available_fields, get_process, get_process_fields,
    list_processes, remove_field_from_process,
    save_tags, set_ticket_form, set_ticket_group, update_process,
    update_process_field,
)

router = APIRouter(prefix="/zendesk", tags=["Zendesk — Processes"])

_read  = [Depends(require_permission("zendesk:read"))]
_write = [Depends(require_permission("zendesk:admin"))]


# ── Processes (nested under instance) ────────────────────────────────────────

@router.get("/instances/{instance_id}/processes", response_model=list[ProcessOut], dependencies=_read)
async def list_processes_endpoint(instance_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await list_processes(conn, instance_id)


@router.post("/instances/{instance_id}/processes", response_model=ProcessOut, status_code=201, dependencies=_write)
async def create_process_endpoint(
    instance_id: int,
    body: ProcessCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    async with request.app.state.pool.acquire() as conn:
        return await create_process(conn, instance_id, body.model_dump(), current_user["id"])


@router.get("/processes/{process_id}", response_model=ProcessOut, dependencies=_read)
async def get_process_endpoint(process_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await get_process(conn, process_id)


@router.patch("/processes/{process_id}", response_model=ProcessOut, dependencies=_write)
async def update_process_endpoint(process_id: int, body: ProcessUpdate, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await update_process(conn, process_id, body.model_dump(exclude_none=True))


@router.delete("/processes/{process_id}", status_code=204, dependencies=_write)
async def delete_process_endpoint(process_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await delete_process(conn, process_id)


# ── Field configuration ───────────────────────────────────────────────────────

@router.get("/processes/{process_id}/fields", dependencies=_read)
async def get_process_fields_endpoint(process_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await get_process_fields(conn, process_id)


@router.get("/processes/{process_id}/fields/available", dependencies=_read)
async def get_available_fields_endpoint(process_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await get_available_fields(conn, process_id)


@router.post("/processes/{process_id}/fields", status_code=204, dependencies=_write)
async def add_field_endpoint(process_id: int, body: AddFieldRequest, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await add_field_to_process(conn, process_id, body.field_id)


@router.patch("/processes/{process_id}/fields/{field_id}", status_code=204, dependencies=_write)
async def update_field_endpoint(
    process_id: int, field_id: int, body: UpdateFieldRequest, request: Request
):
    async with request.app.state.pool.acquire() as conn:
        await update_process_field(conn, process_id, field_id, body.default_value, body.user_visible)


@router.delete("/processes/{process_id}/fields/{field_id}", status_code=204, dependencies=_write)
async def remove_field_endpoint(process_id: int, field_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await remove_field_from_process(conn, process_id, field_id)


# ── Tags, form, group ─────────────────────────────────────────────────────────

@router.put("/processes/{process_id}/tags", status_code=204, dependencies=_write)
async def save_tags_endpoint(process_id: int, body: SetTagsRequest, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await save_tags(conn, process_id, body.tags)


@router.patch("/processes/{process_id}/form", status_code=204, dependencies=_write)
async def set_form_endpoint(process_id: int, body: SetFormRequest, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await set_ticket_form(conn, process_id, body.ticket_form_id)


@router.patch("/processes/{process_id}/group", status_code=204, dependencies=_write)
async def set_group_endpoint(process_id: int, body: SetGroupRequest, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await set_ticket_group(conn, process_id, body.ticket_group_id)
