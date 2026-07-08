from pydantic import BaseModel
from datetime import datetime


class RoleCreate(BaseModel):
    name: str
    description: str | None = None
    
class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    permissions: list[str] = []
    created_at: datetime
    
class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    
class PermissionAssignRequest(BaseModel):
    permission_id: int
    
class UserRoleAssignRequest(BaseModel):
    role_id: int