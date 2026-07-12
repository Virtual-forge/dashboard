import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    database_url = os.environ["DATABASE_URL"]
    print(f"Connecting to database...")
    conn = await asyncpg.connect(database_url)
    try:
        print("Reading migrations.sql...")
        with open("migrations.sql", "r") as f:
            sql = f.read()
        print("Executing migrations...")
        await conn.execute(sql)
        print("Migrations executed successfully!")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
