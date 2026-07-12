import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    database_url = os.environ["DATABASE_URL"]
    conn = await asyncpg.connect(database_url)
    try:
        # Check if table exists and print its columns
        row = await conn.fetchrow("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'ai' 
                AND table_name = 'agno_approvals'
            );
        """)
        exists = row[0] if row else False
        print(f"Table ai.agno_approvals exists: {exists}")
        if exists:
            columns = await conn.fetch("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'ai' 
                AND table_name = 'agno_approvals';
            """)
            print("Columns:")
            for col in columns:
                print(f"  {col['column_name']}: {col['data_type']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
