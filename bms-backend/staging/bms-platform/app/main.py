from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from core.logging import configure_logging
from database.pool import create_pool, close_pool
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
    yield
    await close_pool(app.state.pool)

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

app.middleware("http")(request_id_middleware)

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS_MAP.get(type(exc), 500),
        content={
            "error": exc.code,
            "message": exc.message,
        },
    )
    
app.include_router(monitoring_router, prefix="/api/v1", tags="system_checks")