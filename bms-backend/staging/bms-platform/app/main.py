from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

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

from app.auth.routers import router as auth_router
from app.users.routers import router as users_router
from app.rbac.routers import router as rbac_router
from app.zendesk.routers.instances import router as zd_instances_router
from app.zendesk.routers.processes import router as zd_processes_router
from app.zendesk.routers.operations import router as zd_operations_router

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
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await close_pool(app.state.pool)
    await app.state.redis.aclose()


app = FastAPI(
    title="BMS Platform",
    description="Backend services powering the BMS platform",
    version="1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(",") if settings.allowed_origins else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

app.middleware("http")(request_id_middleware)
app.middleware("http")(error_handler_middleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS_MAP.get(type(exc), 500),
        content={"error": exc.code, "message": exc.message},
    )


PREFIX = "/api/v1"

app.include_router(monitoring_router, prefix=PREFIX, tags=["System"])
app.include_router(auth_router,          prefix=PREFIX)
app.include_router(users_router,         prefix=PREFIX)
app.include_router(rbac_router,          prefix=PREFIX)
app.include_router(zd_instances_router,  prefix=PREFIX)
app.include_router(zd_processes_router,  prefix=PREFIX)
app.include_router(zd_operations_router, prefix=PREFIX)


# -- Swagger UI: add Bearer token authorization button ---------------------
from fastapi.openapi.utils import get_openapi


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    # Stamp every operation so Swagger actually sends the token
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation["security"] = [{"bearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi
