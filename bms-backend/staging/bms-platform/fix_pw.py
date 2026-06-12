import asyncio, asyncpg, os
from passlib.context import CryptContext

async def main():
    pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
    h = pwd.hash("Admin@1234")
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE email = 'jesskurere@gmail.com'",
        h
    )
    print("Done. Hash:", h[:20], "...")
    await conn.close()

asyncio.run(main())
