import asyncio
import asyncpg
import os
import json
from dotenv import load_dotenv

load_dotenv()

async def main():
    database_url = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(database_url)
    try:
        row = await conn.fetchrow("SELECT * FROM ai.agno_approvals LIMIT 1")
        if row:
            print("Row data:")
            for k, v in dict(row).items():
                print(f"  {k}: {v} ({type(v)})")
        else:
            print("No rows found in ai.agno_approvals")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
