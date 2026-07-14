import asyncpg
import structlog
from app.config import get_settings

logger = structlog.get_logger()

async def create_pool() -> asyncpg.Pool:
    """Db connection pool creation"""
    settings = get_settings()
    logger.info("Creating database pool", host=settings.postgres_host)
    pool = await asyncpg.create_pool(
        # dsn=settings.DATABASE_URL, Suitable for production
        # Connecting to the local dockerized postgres database
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        min_size=3,
        max_size=20,
        timeout=30,
        max_inactive_connection_lifetime=300.0,
        command_timeout=8,
        server_settings={
            "application_name": "bms-platform",
            "jit": "off"
        }
    )   
    logger.info("database_pool_created_successfully")
    return pool
    
async def close_pool(pool: asyncpg.Pool) -> None:
    logger.info("closing_database_pool")
    await pool.close() 
    logger.info("database_pool_closed_successfully")
    