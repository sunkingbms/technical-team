import asyncpg
from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_pool, require_permission
from app.zendesk.schemas import (
    OperationCreate, OperationResponse, OperationRowsResponse,
    SheetListResponse, SheetPreviewRequest, SheetPreviewResponse,
)
from app.zendesk.services.operation_service import (
    cancel_operation, create_operation, get_operation, get_operation_rows, list_operations,
)
from app.zendesk.services.sheets_client import fetch_sheet_data, list_sheet_tabs

router = APIRouter(prefix="/zendesk", tags=["Zendesk — Operations"])

_read = Depends(require_permission("zendesk:read"))


@router.get("/operations", status_code=status.HTTP_200_OK)
async def list_operations_endpoint(
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _read,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    async with pool.acquire() as conn:
        return await list_operations(conn, skip=skip, limit=limit)


@router.post("/operations", response_model=OperationResponse, status_code=status.HTTP_201_CREATED)
async def create_operation_endpoint(
    body: OperationCreate,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(require_permission("zendesk:create")),
):
    async with pool.acquire() as conn:
        return await create_operation(
            conn,
            instance_id=body.instance_id,
            process_id=body.process_id,
            start_date=body.start_date,
            sheet_id=body.sheet_id,
            sheet_name=body.sheet_name,
            field_mapping=body.field_mapping,
            created_by=current_user["id"],
        )


@router.get("/operations/{operation_id}", response_model=OperationResponse, status_code=status.HTTP_200_OK)
async def get_operation_endpoint(
    operation_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _read,
):
    async with pool.acquire() as conn:
        return await get_operation(conn, operation_id)


@router.delete("/operations/{operation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_operation_endpoint(
    operation_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(require_permission("zendesk:create")),
):
    async with pool.acquire() as conn:
        await cancel_operation(conn, operation_id)


@router.get("/operations/{operation_id}/rows", response_model=OperationRowsResponse, status_code=status.HTTP_200_OK)
async def get_operation_rows_endpoint(
    operation_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = _read,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    async with pool.acquire() as conn:
        return await get_operation_rows(conn, operation_id, skip=skip, limit=limit)


# ── Google Sheets helpers (list tabs + preview rows) ─────────────────────────

@router.get("/sheets/list", response_model=SheetListResponse, status_code=status.HTTP_200_OK)
async def sheet_list(
    sheet_id: str = Query(..., description="Google Sheets spreadsheet ID"),
    current_user: dict = Depends(require_permission("zendesk:create")),
):
    """Return the list of tab names in a spreadsheet."""
    sheets = await list_sheet_tabs(sheet_id)
    return SheetListResponse(sheets=sheets)


@router.post("/sheets/preview", response_model=SheetPreviewResponse, status_code=status.HTTP_200_OK)
async def sheet_preview(
    body: SheetPreviewRequest,
    current_user: dict = Depends(require_permission("zendesk:create")),
):
    data = await fetch_sheet_data(body.sheet_id, body.sheet_name)
    return SheetPreviewResponse(
        headers=data["headers"],
        row_count=len(data["rows"]),
        preview=data["rows"][:10],
    )
