"""
Minimal connection diagnostic. Run this from the backend/ folder:
    python debug_connection.py

It does the smallest possible steps one at a time, printing after each,
so we can see exactly which step triggers "connection closed mid operation".
"""
import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


async def main():
    print(f"Connecting to: {DATABASE_URL.split('@')[-1]}")  # hides credentials
    conn = await asyncpg.connect(DATABASE_URL)
    print("Step 1: connected OK")

    val = await conn.fetchval("SELECT 1")
    print(f"Step 2: SELECT 1 -> {val}")

    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_schema = 'ai' AND table_name = 'tool_descriptions')"
    )
    print(f"Step 3: tool_descriptions table exists? -> {exists}")

    if exists:
        count = await conn.fetchval("SELECT count(*) FROM ai.tool_descriptions")
        print(f"Step 4: current row count -> {count}")

        await conn.execute(
            """
            INSERT INTO ai.tool_descriptions (tool_name, description, updated_at)
            VALUES ($1, $2, now())
            ON CONFLICT (tool_name)
            DO UPDATE SET description = EXCLUDED.description, updated_at = now()
            """,
            "debug_test_tool",
            "This is a test row inserted by debug_connection.py",
        )
        print("Step 5: test insert/upsert OK")

        await conn.execute("DELETE FROM ai.tool_descriptions WHERE tool_name = $1", "debug_test_tool")
        print("Step 6: test cleanup delete OK")

    await conn.close()
    print("Step 7: closed cleanly")


if __name__ == "__main__":
    asyncio.run(main())
