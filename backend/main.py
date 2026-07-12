import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # must run before importing auth/database, which read env vars at import time

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from auth import create_token, get_current_admin_email, verify_password
from database import close_pool, get_pool, init_pool
from models import ApprovalOut, LoginRequest, LoginResponse, ResolveRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Agent Approval Dashboard API", lifespan=lifespan)

# In production, replace "*" with your actual frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def row_to_approval(row) -> dict:
    data = dict(row)
    tool_args = data.get("tool_args")
    if isinstance(tool_args, str):
        data["tool_args"] = json.loads(tool_args) if tool_args else {}
    elif tool_args is None:
        data["tool_args"] = {}
        
    context = data.get("context")
    if isinstance(context, dict):
        data["context"] = json.dumps(context)
    elif isinstance(context, str):
        pass
    else:
        data["context"] = None
        
    data["id"] = str(data["id"])
    return data


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email, password_hash FROM admins WHERE email = $1", body.email
        )
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(row["email"])
    return LoginResponse(token=token, email=row["email"])


@app.get("/api/approvals", response_model=list[ApprovalOut])
async def list_approvals(
    status: str = Query("pending", description="pending | approved | rejected | all"),
    admin_email: str = Depends(get_current_admin_email),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        if status == "all":
            rows = await conn.fetch(
                """
                SELECT a.id, a.run_id, a.agent_id, a.tool_name, td.description AS tool_description,
                       a.tool_args, a.context, a.user_id as requested_by, a.status, a.resolved_by,
                       to_timestamp(a.resolved_at) as resolved_at, to_timestamp(a.created_at) as created_at
                FROM ai.agno_approvals a
                LEFT JOIN tool_descriptions td ON td.tool_name = a.tool_name
                ORDER BY a.created_at DESC
                LIMIT 200
                """
            )
        else:
            rows = await conn.fetch(
                """
                SELECT a.id, a.run_id, a.agent_id, a.tool_name, td.description AS tool_description,
                       a.tool_args, a.context, a.user_id as requested_by, a.status, a.resolved_by,
                       to_timestamp(a.resolved_at) as resolved_at, to_timestamp(a.created_at) as created_at
                FROM ai.agno_approvals a
                LEFT JOIN tool_descriptions td ON td.tool_name = a.tool_name
                WHERE a.status = $1
                ORDER BY a.created_at DESC
                LIMIT 200
                """,
                status,
            )
    return [row_to_approval(r) for r in rows]


@app.post("/api/approvals/{approval_id}/resolve", response_model=ApprovalOut)
async def resolve_approval(
    approval_id: str,
    body: ResolveRequest,
    admin_email: str = Depends(get_current_admin_email),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        # expected_status check prevents two admins racing on the same request
        row = await conn.fetchrow(
            """
            WITH updated AS (
                UPDATE ai.agno_approvals
                SET status = $1, resolved_by = $2, resolved_at = extract(epoch from $3::timestamptz)::bigint
                WHERE id = $4 AND status = 'pending'
                RETURNING id, run_id, agent_id, tool_name, tool_args, context,
                          user_id, status, resolved_by, resolved_at, created_at
            )
            SELECT u.id, u.run_id, u.agent_id, u.tool_name, td.description AS tool_description,
                   u.tool_args, u.context, u.user_id as requested_by, u.status, u.resolved_by,
                   to_timestamp(u.resolved_at) as resolved_at,
                   to_timestamp(u.created_at) as created_at
            FROM updated u
            LEFT JOIN tool_descriptions td ON td.tool_name = u.tool_name
            """,
            body.decision,
            admin_email,
            datetime.now(timezone.utc),
            approval_id,
        )
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Request not found or already resolved by someone else",
        )
    return row_to_approval(row)
