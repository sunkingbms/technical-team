"""
This should be ran manually once on first deploy and after every new migration file is added.
How to run it:
- docker compose exec api python -m app.database.migrations.run_migrations
"""
import asyncio
import os
import asyncpg
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent


async def run():
    dsn = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(dsn)

    # Create tracking table if it doesn't exist
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   VARCHAR(255) PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Get already-applied migrations
    applied = {
        row["filename"]
        for row in await conn.fetch("SELECT filename FROM schema_migrations")
    }

    # Get all .sql files, sorted by name (001_, 002_, etc.)
    migration_files = sorted(
        f for f in MIGRATIONS_DIR.glob("*.sql")
    )

    applied_count = 0
    for filepath in migration_files:
        filename = filepath.name
        if filename in applied:
            print(f"  skip  {filename}")
            continue
        print(f"  apply {filename}")
        sql = filepath.read_text()
        await conn.execute(sql)
        await conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES ($1)", filename
        )
        applied_count += 1
    
    await conn.close()
    print(f"Applied {applied_count} migrations")


if __name__ == "__main__":
    asyncio.run(run())