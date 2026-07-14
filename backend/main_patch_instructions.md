# Exact changes to backend/main.py

Everything else in main.py stays the same. Only the imports and the
`lifespan` function change, plus one line to mount the webhook router.

## 1. Add imports (top of file, with your other imports)
```python
import asyncio
from approval_listener import run_approval_listener
from jira_webhook import router as jira_router
from database import DATABASE_URL   # you likely already have this in database.py;
                                     # if not, just read os.environ["DATABASE_URL"] here too
```

## 2. Update lifespan (currently just calls init_pool/close_pool)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    listener_task = asyncio.create_task(run_approval_listener(DATABASE_URL))
    yield
    listener_task.cancel()
    await close_pool()
```

## 3. Mount the webhook router (anywhere after `app = FastAPI(...)`)
```python
app.include_router(jira_router)
```

## 4. Wire jira_webhook.py's get_db_pool() to your real pool
In jira_webhook.py, replace:
```python
async def get_db_pool():
    raise NotImplementedError(...)
```
with:
```python
from database import get_pool

async def get_db_pool():
    return get_pool()
```

That's it -- no new process, no new port. When you run your dashboard
backend the way you already do (uvicorn main:app ...), the Jira listener
starts automatically as a background task inside it.
