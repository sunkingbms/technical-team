import asyncpg
from fastapi import APIRouter, Depends, status, Response, Query

from app.users.schemas import UserCreate, UserUpdate, UserResponse, PaginatedUsersResponse
from app.users import repository as users_rep
from app.dependencies import get_pool, get_current_user, require_permission
from core.exceptions import NotFoundError, ErrorCodes
from app.auth.utils import password_hash
from fastapi import Response


router = APIRouter(
    prefix="/users"
)

################### GET ENDPOINTS ###################

@router.get("/", status_code=status.HTTP_200_OK, response_model=PaginatedUsersResponse)
async def get_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: dict = Depends(require_permission("users:read")),
    pool: asyncpg.Pool = Depends(get_pool)
):
    """Returns a paginated list of users."""
    offset = (page - 1) * page_size
    async with pool.acquire() as conn:
        users, total = await users_rep.get_all_users(conn, page_size, offset)
    
    return PaginatedUsersResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=-(-total // page_size)
    )
    
@router.get("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
async def get_user_by_id(user_id: int, pool: asyncpg.Pool = Depends(get_pool), _: dict = Depends(require_permission("users:read"))):
    """Returns a user by their ID, raise NotFoundError if missing."""
    async with pool.acquire() as conn:
        return await users_rep.get_user_by_id(conn, user_id)
    
    
################### POST ENDPOINTS ###################

@router.post('/', status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(body: UserCreate, pool: asyncpg.Pool = Depends(get_pool), _: dict = Depends(require_permission("users:write"))):
    """Creates a new user with a hashed password, raise ConflictError if user already exists."""
    hashed_password = password_hash(body.password)
    async with pool.acquire() as conn:
        return await users_rep.create_user(conn, body.email, hashed_password, body.full_name)
    
################### PUT ENDPOINTS ###################

@router.patch("/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse)
async def update_user(user_id: int, body: UserUpdate, pool: asyncpg.Pool = Depends(get_pool), _: dict = Depends(require_permission("users:write"))):
    """Updates a user's information, raise ConflictError if user email already exists."""
    fields = body.model_dump(exclude_unset=True)
    async with pool.acquire() as conn:
        return await users_rep.update_user(conn, user_id, **fields)
    
################### DELETE ENDPOINTS ###################

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, pool: asyncpg.Pool = Depends(get_pool), _: dict = Depends(require_permission("users:delete"))):
    """Deletes a user, returns True if deleted, False if not found."""
    async with pool.acquire() as conn:
        deleted = await users_rep.delete_user(conn, user_id)
        if not deleted:
            raise NotFoundError(message="User not found", code=ErrorCodes.USER_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

