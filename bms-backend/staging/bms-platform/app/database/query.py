import time
import structlog
import asyncpg
from prometheus_client import Counter

logger = structlog.get_logger()

SLOW_QUERY_THRESHOLD=150

SLOW_QUERY_COUNTER = Counter(
    "slow_queries_total",
    "Database queries exceeding the slow query threshold",
    ["label"]
)

def _log_if_slow(label: str, start: float) -> None:
    duration_ms = (time.monotonic() - start) * 1000
    if duration_ms > SLOW_QUERY_THRESHOLD:
        SLOW_QUERY_COUNTER.labels(label=label).inc()

async def fetch_row(conn: asyncpg.Connection, query: str, *args, label: str = "unlabeled") -> asyncpg.Record | None:
    start = time.monotonic()
    result = await conn.fetchrow(query, *args)
    _log_if_slow(label, start)
    return result

async def fetch(conn: asyncpg.Connection, query: str, *args, label="unlabeled") -> list[asyncpg.Record]:
    start = time.monotonic()
    result = await conn.fetch(query, *args)
    _log_if_slow(label, start)
    return result

async def execute(conn: asyncpg.Connection, query: str, *args,label="unlabeled") -> str:
    start = time.monotonic()
    result = await conn.execute(query, *args)
    _log_if_slow(label, start)
    return result


async def fetchval(conn: asyncpg.Connection, query: str, *args, label: str = "unlabeled"):
    start = time.monotonic()
    result = await conn.fetchval(query, *args)
    _log_if_slow(label, start)
    return result