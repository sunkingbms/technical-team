from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RoleOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime


class PermissionOut(BaseModel):
    id: int
    codename: str
    description: Optional[str] = None


class AddPermissionRequest(BaseModel):
    permission_id: int


class AssignRoleRequest(BaseModel):
    role_id: int
