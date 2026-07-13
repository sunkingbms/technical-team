import asyncpg
from fastapi import APIRouter, Depends, status

from app.dependencies import get_pool, require_permission
from app.zendesk import repository as zendesk_repo
from app.zendesk.schemas import InstanceCreate, InstanceUpdate, InstanceResponse
from app.zendesk.crypto import encrypt_token
from core.exceptions import NotFoundError, ConflictError, ErrorCodes
from app.zendesk.services.instance_service import (
    refresh_all, refresh_fields_only, refresh_forms_only, refresh_groups_only,
)

router = APIRouter(
    prefix="/zendesk",
)

############# GET ENDPOINTS ##################
@router.get("/instances", status_code=status.HTTP_200_OK, response_model=list[InstanceResponse])
async def get_instances(
    pool: asyncpg.Pool = Depends(get_pool), 
    current_user: dict = Depends(require_permission("zendesk:read"))
) -> list[dict]:
    """Endpoint returning all created zendesk instances."""
    async with pool.acquire() as conn:
        instances = await zendesk_repo.get_all_instances(conn)
        return instances

@router.get("/instances/{instance_id}", status_code=status.HTTP_200_OK, response_model=InstanceResponse)
async def get_instance(
    instance_id: int, 
    pool: asyncpg.Pool = Depends(get_pool), 
    current_user: dict = Depends(require_permission("zendesk:read"))
):
    """Endpoint returning a single zendesk instance by ID."""
    async with pool.acquire() as conn:
        instance = await zendesk_repo.get_instance_by_id(conn, instance_id)
    return instance


############# POST ENDPOINTS ##################
@router.post("/instances", status_code=status.HTTP_201_CREATED, response_model=InstanceResponse)
async def create_instance(
    body: InstanceCreate, 
    pool: asyncpg.Pool = Depends(get_pool),
    current_user: dict = Depends(require_permission("zendesk:admin"))
) -> dict:
    """Endpoint creating a new zendesk instance."""
    encrypted_api_token = encrypt_token(body.api_token)
    async with pool.acquire() as conn:
        return await zendesk_repo.create_instance(
            conn,
            body.name,
            body.subdomain,
            body.email,
            encrypted_api_token,
            current_user["id"]
        )
        
        
@router.post("/instances/{instance_id}/refresh", status_code=status.HTTP_200_OK)
async def refresh_instance_metadata(
    instance_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("zendesk:admin"))
):
    """Endpoint refreshing all metadata (fields + forms + groups) for a single zendesk instance by ID."""
    async with pool.acquire() as conn:
        await refresh_all(conn, instance_id)
    return {"message": "Metadata refreshed successfully"}


@router.post("/instances/{instance_id}/refresh-fields", status_code=status.HTTP_200_OK)
async def refresh_instance_fields(
    instance_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("zendesk:admin"))
):
    """Endpoint refreshing just the ticket fields for a single zendesk instance by ID."""
    async with pool.acquire() as conn:
        await refresh_fields_only(conn, instance_id)
    return {"message": "Fields refreshed successfully"}


@router.post("/instances/{instance_id}/refresh-forms", status_code=status.HTTP_200_OK)
async def refresh_instance_forms(
    instance_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("zendesk:admin"))
):
    """Endpoint refreshing just the ticket forms for a single zendesk instance by ID."""
    async with pool.acquire() as conn:
        await refresh_forms_only(conn, instance_id)
    return {"message": "Forms refreshed successfully"}


@router.post("/instances/{instance_id}/refresh-groups", status_code=status.HTTP_200_OK)
async def refresh_instance_groups(
    instance_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("zendesk:admin"))
):
    """Endpoint refreshing just the groups for a single zendesk instance by ID."""
    async with pool.acquire() as conn:
        await refresh_groups_only(conn, instance_id)
    return {"message": "Groups refreshed successfully"}


############# PATCH ENDPOINTS ##################
@router.patch("/instances/{instance_id}", status_code=status.HTTP_200_OK, response_model=InstanceResponse)
async def update_instance(
    instance_id: int,
    body: InstanceUpdate,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("zendesk:admin"))
):
    """Endpoint updating a single zendesk instance by ID."""
    fields = body.model_dump(exclude_unset=True)
    
    if "api_token" in fields:
        fields["encrypted_api_token"] = encrypt_token(fields.pop("api_token"))
    
    async with pool.acquire() as conn:
        return await zendesk_repo.update_instance(
            conn,
            instance_id,
            **fields
        )
        
############# DELETE ENDPOINTS ##################
@router.delete("/instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instance(
    instance_id: int,
    pool: asyncpg.Pool = Depends(get_pool),
    _: dict = Depends(require_permission("zendesk:delete"))
):
    """Endpoint deleting a single zendesk instance by ID."""
    async with pool.acquire() as conn:
        await zendesk_repo.soft_delete_instance(conn, instance_id)