import time
import uuid
import asyncpg
import structlog
from fastapi import Request, Response
from starlette.background import BackgroundTask
from app.database.query import execute


logger = structlog.get_logger()

EXCLUDED_PATHS = {"/docs", "/openapi.json", "/api/v1/health", "/metrics", "/redoc"}

async def _write_audit_to_table(pool: asyncpg.Pool, query, user_id: int, request_id: uuid.UUID, resource: str, status_code: int, duration_ms: float, action: str, ip_address: str, user_agent: str, label="unlabeled") -> None:
    """Background task used to write audit log to the db"""
    try:
        async with pool.acquire() as conn:
            await execute(conn, query, user_id, request_id, resource, status_code, duration_ms, action, ip_address, user_agent, label="inserting_audit_log")
    except Exception as e:
        logger.warning("Error writing audit log to the table", error=e)


async def audit_middleware(request: Request, call_next):
    
    if request.method == "GET" or request.url.path in EXCLUDED_PATHS:
        return await call_next(request)
        
    
    start_time = time.monotonic()
    
    # Below we are passing the control to the application(All our endpoints are handled by this call_next function)
    response = await call_next(request)
    
    # Getting the time it took to process the request
    duration_ms = (time.monotonic() - start_time) * 1000
    
    # Extracting request_id 
    raw_request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    # Check if the request_id is a valid UUID if not create a new one
    try:
        parsed_request_id = uuid.UUID(raw_request_id)
    except ValueError:
        parsed_request_id = uuid.uuid4()
        
    # Extracting user_id from the request object
    user_data = getattr(request.state, "user", None)
    
    user_id = user_data["id"] if user_data else None
    ip_address = request.client.host if request.client else None
    
    user_agent = request.headers.get('user-agent', '')
    
    resource = getattr(request.state, "resource", None)
    
    action = f"{request.method.lower()}.{request.url.path.strip('/').replace('/', '.')}"
    
    # Writing to the audit log table
    query = "INSERT INTO audit_log (user_id, request_id, resource, status_code, duration_ms, action, ip_address, user_agent) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
    
    response.background = BackgroundTask(
        _write_audit_to_table, 
        request.app.state.pool, 
        query, 
        user_id, 
        parsed_request_id, 
        resource, 
        response.status_code, 
        duration_ms, 
        action, 
        ip_address, 
        user_agent, 
        label="inserting_audit_log"
    )
    
    # Structured log for real-time monitoring (happens immediately)
    logger.info(
        "audit_request",
        user_id=user_id,
        action=action,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2)
    )
    
    return response
    
    