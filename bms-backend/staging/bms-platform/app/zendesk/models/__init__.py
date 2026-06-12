"""Pydantic schemas for the Zendesk module."""
from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import date, datetime
from enum import Enum


# ── Instances ─────────────────────────────────────────────────────────────────

class InstanceCreate(BaseModel):
    instance_name: str
    subdomain: str = Field(..., description="e.g. mycompany.zendesk.com")
    email: str
    access_token: str


class InstanceUpdate(BaseModel):
    instance_name: Optional[str] = None
    subdomain: Optional[str] = None
    email: Optional[str] = None
    access_token: Optional[str] = None


class InstanceOut(BaseModel):
    id: int
    instance_name: str
    subdomain: str
    email: str
    process_count: int = 0
    field_count: int = 0
    forms_count: int = 0
    groups_count: int = 0
    created_at: datetime


class RefreshResponse(BaseModel):
    status: str
    message: str


# ── Processes ─────────────────────────────────────────────────────────────────

class OperationType(str, Enum):
    create = "create"
    delete = "delete"


class ProcessStatus(str, Enum):
    active = "ACTIVE"
    inactive = "INACTIVE"


class ProcessCreate(BaseModel):
    process_name: str
    process_description: Optional[str] = None
    operation: OperationType
    status: ProcessStatus = ProcessStatus.active


class ProcessUpdate(BaseModel):
    process_name: Optional[str] = None
    process_description: Optional[str] = None
    operation: Optional[OperationType] = None
    status: Optional[ProcessStatus] = None


class ProcessOut(BaseModel):
    id: int
    instance_id: int
    process_name: str
    process_description: Optional[str] = None
    operation: str
    status: str
    ticket_form_id: Optional[int] = None
    ticket_group_id: Optional[int] = None
    fields_count: int = 0
    created_at: datetime


# ── Process field config ──────────────────────────────────────────────────────

class AddFieldRequest(BaseModel):
    field_id: int   # references zd_fields.id


class UpdateFieldRequest(BaseModel):
    default_value: Optional[str] = None
    user_visible: Optional[bool] = None


class ProcessFieldOut(BaseModel):
    id: int
    field_id: int
    zendesk_field_id: int
    title: str
    type: str
    default_value: Optional[str] = None
    user_visible: bool


class SetFormRequest(BaseModel):
    ticket_form_id: Optional[int] = None


class SetGroupRequest(BaseModel):
    ticket_group_id: Optional[int] = None


class SetTagsRequest(BaseModel):
    tags: list[str]


# ── Operations ────────────────────────────────────────────────────────────────

class OperationCreate(BaseModel):
    instance_id: int
    process_id: int
    start_date: date
    sheet_id: str = Field(..., description="Google Sheets spreadsheet ID")
    sheet_name: str = Field(..., description="Sheet tab name")
    # For 'create' processes: {zendesk_field_id_str: col_index}
    # For 'delete' processes: {"delete_column": col_index}
    field_mapping: dict[str, int]


class OperationOut(BaseModel):
    id: int
    zendesk_instance_id: int
    process_id: int
    instance_name: str
    operation: str
    status: str
    item_count: int
    processed_count: int
    start_date: Optional[date] = None
    created_by_email: Optional[str] = None
    created_at: datetime


class OperationRowOut(BaseModel):
    id: int
    status: str
    ticket_id: Optional[int] = None
    columns: dict[str, Any]   # col_0..col_19 as present


class OperationRowsOut(BaseModel):
    total: int
    items: list[OperationRowOut]


# ── Google Sheets preview ─────────────────────────────────────────────────────

class SheetPreviewRequest(BaseModel):
    sheet_id: str
    sheet_name: str


class SheetPreviewResponse(BaseModel):
    headers: list[str]
    row_count: int
    preview: list[list[str]]  # first 10 rows
