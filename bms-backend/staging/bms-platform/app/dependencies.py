from fastapi import Request
import asyncpg



# The below function ensures that the database pool is available for the request lifespan
# In other way it retrieves database connection stored inside FastAPI application instance
async def get_pool(request: Request) -> asyncpg.Pool:
    """Dependency to get the database pool"""
    return request.app.state.pool