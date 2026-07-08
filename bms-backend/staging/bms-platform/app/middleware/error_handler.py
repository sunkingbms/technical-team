import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from app.config import get_settings


logger = structlog.get_logger()

async def error_handler_middleware(request: Request, call_next) -> JSONResponse:
    """Handle errors gracefully and return JSON responses"""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        settings = get_settings()
        
        logger.exception(
            "unhandled_exception", 
            method=request.method,
            path=request.url.path,
            error=str(e)
        )
        
        content = {
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred"
        }
        
        if settings.app_env == "development":
            content["details"] = str(e)
        
        
        
        return JSONResponse(status_code=500, content=content)