import structlog
import redis as redis_lib
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
import asyncpg

from app.config import get_settings
from app.dependencies import get_pool

router = APIRouter()
logger = structlog.get_logger()

@router.get(
    "/health",
    summary="System health check",
    description="Verifies database, Redis, and Celery are healthy",
    responses={
        200: {"description": "All components are healthy"},
        503: {"description": "One or more components are unhealthy"},
    }
)
async def health_check(pool: asyncpg.Pool = Depends(get_pool)) -> JSONResponse:
    """Check if the system is healthy"""
    settings = get_settings()
    checks = {}
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
        logger.error("health_check_database_failed", error=str(e))
    
    try:
        r = redis_lib.from_url(settings.redis_url + "/0")
        r.setex("health_check_probe", 5, "1")
        value = r.get("health_check_probe")
        if value == b"1":
            checks["redis"] = "ok"
        else:
            checks["redis"] = f"error: {type(e).__name__}"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"
        logger.error("health_check_redis_failed", error=str(e))
    
    try:
        from celery_worker.celery_app import app as celery_app
        inspector = celery_app.control.inspect(timeout=2.0)
        active = inspector.active()
        
        if active:
            checks["celery"] = "ok"
        else:
            checks["celery"] = "no workers active"
            logger.warning("health_check_celery_no_workers")
    except Exception as e:
        checks["celery"] = f"error: {type(e).__name__}"
        logger.error("health_check_celery_failed", error=str(e))
        
    all_ok = all(status == "ok" for status in checks.values())
    
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "healthy" if all_ok else "unhealthy",
            "checks": checks
        }
    )