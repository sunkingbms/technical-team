import asyncpg
from fastapi import APIRouter, Depends, status

from app.dependencies import get_pool, require_permission
from app.zendesk.schemas import (
    AddFieldRequest, ProcessCreate, ProcessResponse, ProcessUpdate,
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

_read = Depends(require_permission("zendesk:read"))
_write = Depends(require_permission("zendesk:admin"))


# ── Processes (nested under instance) ────────────────────────────────────────

@router.get("/instances/{instance_id}/processes", response_model=list[ProcessResponse], status_code=status.HTTP_200_OK)
async def list_processes_endpoint(
    instance_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _read,
):
    async with pool.acquire() as conn:
        return await list_processes(conn, instance_id)


@router.post("/instances/{instance_id}/processes", response_model=ProcessResponse, status_code=status.HTTP_201_CREATED)
async def create_process_endpoint(
    instance_id: int,
    body: ProcessCreate,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        return await create_process(conn, instance_id, body.model_dump(), current_user["id"])


@router.get("/processes/{process_id}", response_model=ProcessResponse, status_code=status.HTTP_200_OK)
async def get_process_endpoint(
    process_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _read,
):
    async with pool.acquire() as conn:
        return await get_process(conn, process_id)


@router.patch("/processes/{process_id}", response_model=ProcessResponse, status_code=status.HTTP_200_OK)
async def update_process_endpoint(
    process_id: int,
    body: ProcessUpdate,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        return await update_process(conn, process_id, body.model_dump(exclude_none=True))


@router.delete("/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process_endpoint(
    process_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        await delete_process(conn, process_id)


# ── Field configuration ───────────────────────────────────────────────────────

@router.get("/processes/{process_id}/fields", status_code=status.HTTP_200_OK)
async def get_process_fields_endpoint(
    process_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _read,
):
    async with pool.acquire() as conn:
        return await get_process_fields(conn, process_id)


@router.get("/processes/{process_id}/fields/available", status_code=status.HTTP_200_OK)
async def get_available_fields_endpoint(
    process_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _read,
):
    async with pool.acquire() as conn:
        return await get_available_fields(conn, process_id)


@router.post("/processes/{process_id}/fields", status_code=status.HTTP_204_NO_CONTENT)
async def add_field_endpoint(
    process_id: int,
    body: AddFieldRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        await add_field_to_process(conn, process_id, body.field_id)


@router.patch("/processes/{process_id}/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_field_endpoint(
    process_id: int,
    field_id: int,
    body: UpdateFieldRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        await update_process_field(conn, process_id, field_id, body.default_value, body.user_visible)


@router.delete("/processes/{process_id}/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_field_endpoint(
    process_id: int,
    field_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        await remove_field_from_process(conn, process_id, field_id)


# ── Tags, form, group ─────────────────────────────────────────────────────────

@router.put("/processes/{process_id}/tags", status_code=status.HTTP_204_NO_CONTENT)
async def save_tags_endpoint(
    process_id: int,
    body: SetTagsRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        await save_tags(conn, process_id, body.tags)


@router.patch("/processes/{process_id}/form", status_code=status.HTTP_204_NO_CONTENT)
async def set_form_endpoint(
    process_id: int,
    body: SetFormRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        await set_ticket_form(conn, process_id, body.ticket_form_id)


@router.patch("/processes/{process_id}/group", status_code=status.HTTP_204_NO_CONTENT)
async def set_group_endpoint(
    process_id: int,
    body: SetGroupRequest,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _write,
):
    async with pool.acquire() as conn:
        await set_ticket_group(conn, process_id, body.ticket_group_id)
