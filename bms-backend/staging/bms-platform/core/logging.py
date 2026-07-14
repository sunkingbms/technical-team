import logging
import structlog
from app.config import get_settings

def configure_logging(env: str) -> None:
    """
    Configure structlog for the entire application
    """
    
    settings = get_settings()
    
    shared_process = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer()
    ]
    
    if settings.app_env == "development":
        processors = shared_process + [
            structlog.dev.ConsoleRenderer()
        ]
    else:
        processors = shared_process + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class= structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    