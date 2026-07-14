from contextlib import asynccontextmanager

from redis.asyncio import Redis as AsyncRedis

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from core.logging import configure_logging
from app.database.pool import create_pool, close_pool
from core.exceptions import (
    AppError,
    BadRequestError,
    ForbiddenError,
    UnauthorizedError,
    NotFoundError,
    ConflictError,
    InternalServerError,
    ServiceUnavailableError,
    ValidationError,
    ExternalServiceError,
)
from monitoring.routers import router as monitoring_router
from app.middleware.request_id import request_id_middleware
from app.middleware.error_handler import error_handler_middleware

from app.auth.routers.router import router as auth_router
from app.rbac.router import router as rbac_router
from app.users.router import router as users_router
from app.zendesk.router import router as zendesk_router
from app.zendesk.processes_router import router as zendesk_processes_router
from app.zendesk.operations_router import router as zendesk_operations_router

from app.middleware.audit import audit_middleware


settings = get_settings()
configure_logging(settings.app_env)

STATUS_MAP = {
    BadRequestError: 400,
    ForbiddenError: 403,
    UnauthorizedError: 401,
    NotFoundError: 404,
    ConflictError: 409,
    InternalServerError: 500,
    ServiceUnavailableError: 503,
    ValidationError: 422,
    ExternalServiceError: 502,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    app.state.redis = AsyncRedis.from_url(settings.redis_url + "/2", decode_responses=True)
    yield
    await close_pool(app.state.pool)
    await app.state.redis.aclose()

app = FastAPI(
    title="BMS Platform",
    description="Backend services powering the BMS platform",
    version="1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(",") if settings.allowed_origins else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)
app.middleware("http")(audit_middleware)
app.middleware("http")(request_id_middleware)
app.middleware("http")(error_handler_middleware)

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS_MAP.get(type(exc), 500),
        content={
            "error": exc.code,
            "message": exc.message,
        },
    )
    
app.include_router(monitoring_router, prefix="/api/v1", tags=["system_checks"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(rbac_router, prefix="/api/v1", tags=["rbac"])
app.include_router(users_router, prefix="/api/v1", tags=["users"])
app.include_router(zendesk_router, prefix="/api/v1", tags=["zendesk"])
app.include_router(zendesk_processes_router, prefix="/api/v1", tags=["zendesk"])
app.include_router(zendesk_operations_router, prefix="/api/v1", tags=["zendesk"])