import uuid
import structlog
from fastapi import Request
from fastapi.responses import Response


async def request_id_middleware(request: Request, call_next) -> Response:
    """Add a custom request ID to the request context"""
    
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    request.state.request_id = request_id
    
    with structlog.contextvars.bound_contextvars(
        request_id=request_id,
        path=request.url.path,
        method=request.method
    ):
        response = await call_next(request)
        
        response.headers["X-Request-ID"] = request_id
        
        return response