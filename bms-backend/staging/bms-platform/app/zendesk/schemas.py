from pydantic import BaseModel, EmailStr
from datetime import datetime

class InstanceCreate(BaseModel):
    name: str
    subdomain: str
    email: EmailStr
    api_token: str
    
    
class InstanceUpdate(BaseModel):
    name: str | None = None
    subdomain: str | None = None
    email: EmailStr | None = None
    api_token: str | None = None
    
class InstanceResponse(BaseModel):
    id: int
    name: str
    subdomain: str
    email: EmailStr
    is_deleted: bool
    created_at: datetime
    updated_at: datetime