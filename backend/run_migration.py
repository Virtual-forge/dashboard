import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def run_migration():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Read the SQL file
        with open('001_jira_listener_setup.sql', 'r') as f:
            sql = f.read()
        
        # Execute the SQL
        await conn.execute(sql)
        print('Migration executed successfully!')
        
        # Verify the table and trigger were created
        result = await conn.fetch('SELECT * FROM information_schema.tables WHERE table_name = $1', 'jira_sync')
        if result:
            print('jira_sync table EXISTS')
        else:
            print('jira_sync table NOT FOUND')
        
        trigger_result = await conn.fetch('SELECT * FROM information_schema.triggers WHERE event_object_table = $1', 'agno_approvals')
        if trigger_result:
            print('Trigger on agno_approvals EXISTS')
        else:
            print('Trigger on agno_approvals NOT FOUND')
    except Exception as e:
        print(f'Error: {e}')
    finally:
        await conn.close()

asyncio.run(run_migration())