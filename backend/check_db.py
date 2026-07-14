import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def check_table():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        result = await conn.fetch('SELECT * FROM information_schema.tables WHERE table_name = $1', 'jira_sync')
        if result:
            print('jira_sync table EXISTS')
            for row in result:
                print(dict(row))
        else:
            print('jira_sync table NOT FOUND')
        
        # Also check the trigger
        trigger_result = await conn.fetch('SELECT * FROM information_schema.triggers WHERE event_object_table = $1', 'agno_approvals')
        if trigger_result:
            print('Trigger on agno_approvals EXISTS')
            for row in trigger_result:
                print(dict(row))
        else:
            print('Trigger on agno_approvals NOT FOUND')
    finally:
        await conn.close()

asyncio.run(check_table())