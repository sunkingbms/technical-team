from fastapi import APIRouter, Depends, Query, Request

from app.dependencies import get_current_user, require_permission
from app.zendesk.models import (
    OperationCreate, OperationOut, OperationRowsOut, SheetPreviewRequest, SheetPreviewResponse,
)
from app.zendesk.services.operation_service import (
    cancel_operation, create_operation, get_operation, get_operation_rows, list_operations,
)
from app.zendesk.services.sheets_client import fetch_sheet_data

router = APIRouter(prefix="/zendesk", tags=["Zendesk — Operations"])


@router.get("/operations", dependencies=[Depends(require_permission("zendesk:read"))])
async def list_operations_endpoint(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    async with request.app.state.pool.acquire() as conn:
        return await list_operations(conn, skip=skip, limit=limit)


@router.post(
    "/operations",
    response_model=OperationOut,
    status_code=201,
)
async def create_operation_endpoint(
    body: OperationCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    _: dict = Depends(require_permission("zendesk:create")),
):
    async with request.app.state.pool.acquire() as conn:
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


@router.get("/operations/{operation_id}", response_model=OperationOut, dependencies=[Depends(require_permission("zendesk:read"))])
async def get_operation_endpoint(operation_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        return await get_operation(conn, operation_id)


@router.delete("/operations/{operation_id}", status_code=204, dependencies=[Depends(require_permission("zendesk:create"))])
async def cancel_operation_endpoint(operation_id: int, request: Request):
    async with request.app.state.pool.acquire() as conn:
        await cancel_operation(conn, operation_id)


@router.get("/operations/{operation_id}/rows", response_model=OperationRowsOut, dependencies=[Depends(require_permission("zendesk:read"))])
async def get_operation_rows_endpoint(
    operation_id: int,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    async with request.app.state.pool.acquire() as conn:
        return await get_operation_rows(conn, operation_id, skip=skip, limit=limit)


# ── Google Sheets preview (used before operation submission for mapping UI) ───

@router.post(
    "/sheets/preview",
    response_model=SheetPreviewResponse,
    dependencies=[Depends(require_permission("zendesk:create"))],
)
async def sheet_preview(body: SheetPreviewRequest):
    data = await fetch_sheet_data(body.sheet_id, body.sheet_name)
    return SheetPreviewResponse(
        headers=data["headers"],
        row_count=len(data["rows"]),
        preview=data["rows"][:10],
    )
