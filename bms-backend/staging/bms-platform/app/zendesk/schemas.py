from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
import re


def _normalize_zendesk_subdomain(value: str) -> str:
    """
    Accepts a bare subdomain ("mycompany") or something a user might paste from
    their browser ("mycompany.zendesk.com", "https://mycompany.zendesk.com/",
    with trailing slashes/whitespace) and normalizes it down to the bare
    subdomain. ZendeskClient builds the API host as f"{subdomain}.zendesk.com",
    so a subdomain that still has ".zendesk.com" on it produces an invalid
    doubled hostname (e.g. "mycompany.zendesk.com.zendesk.com") that fails to
    resolve/handshake instead of giving a clear error.
    """
    v = value.strip()
    v = re.sub(r"^https?://", "", v, flags=re.IGNORECASE)
    v = v.rstrip("/")
    v = re.sub(r"\.zendesk\.com$", "", v, flags=re.IGNORECASE)
    return v


class InstanceCreate(BaseModel):
    name: str
    subdomain: str
    email: EmailStr
    api_token: str

    @field_validator("subdomain")
    @classmethod
    def normalize_subdomain(cls, v: str) -> str:
        return _normalize_zendesk_subdomain(v)


class InstanceUpdate(BaseModel):
    name: str | None = None
    subdomain: str | None = None
    email: EmailStr | None = None
    api_token: str | None = None

    @field_validator("subdomain")
    @classmethod
    def normalize_subdomain(cls, v: str | None) -> str | None:
        return _normalize_zendesk_subdomain(v) if v is not None else v

class InstanceResponse(BaseModel):
    id: int
    name: str
    subdomain: str
    email: EmailStr
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    process_count: int = 0
    field_count: int = 0
    forms_count: int = 0
    groups_count: int = 0


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


class ProcessResponse(BaseModel):
    id: int
    zendesk_instance_id: int
    process_name: str
    process_description: Optional[str] = None
    operation: str
    status: str
    ticket_form_id: Optional[int] = None
    ticket_group_id: Optional[int] = None
    fields_count: int = 0
    created_at: datetime


# ── Process field / tag / form / group configuration ────────────────────────

class AddFieldRequest(BaseModel):
    field_id: int   # references zendesk_fields.id


class UpdateFieldRequest(BaseModel):
    default_value: Optional[str] = None
    user_visible: Optional[bool] = None


class ProcessFieldResponse(BaseModel):
    id: int
    field_id: int
    zendesk_field_id: int
    title: str
    type: Optional[str] = None
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


class OperationResponse(BaseModel):
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
    headers: Optional[list[str]] = []


class OperationRowResponse(BaseModel):
    id: int
    status: str
    ticket_id: Optional[int] = None
    columns: dict[str, Any]   # col_0..col_19 as present


class OperationRowsResponse(BaseModel):
    total: int
    items: list[OperationRowResponse]


# ── Google Sheets preview ─────────────────────────────────────────────────────

class SheetPreviewRequest(BaseModel):
    sheet_id: str
    sheet_name: str


class SheetListResponse(BaseModel):
    sheets: list[str]


class SheetPreviewResponse(BaseModel):
    headers: list[str]
    row_count: int
    preview: list[dict]  # rows as {column: value} objects