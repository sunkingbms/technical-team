import structlog
from fastapi import Request

logger = structlog.get_logger()


async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    return response
