"""
Dashboard endpoints backed by Jira instead of Postgres directly.

Mount alongside your existing routes:
    from jira_dashboard import router as jira_dashboard_router
    app.include_router(jira_dashboard_router)

Design: the dashboard's "Approve"/"Reject" buttons transition the Jira
issue -- they do NOT write to ai.agno_approvals directly. Your existing
Jira Automation rule (issue transitioned -> webhook -> jira_webhook.py)
is what actually resolves the Postgres row, exactly the same as if a
human clicked the transition inside Jira itself. This keeps Jira as the
single source of truth for the *decision*, regardless of which UI made it.

    Dashboard "Approve" click
            |
            v
    POST /api/jira/approvals/{key}/resolve
            |
            v
    jira_client.transition_issue(key, "Approved")
            |
            v
    (Jira Automation rule fires, same as any other transition)
            |
            v
    jira_webhook.py -> UPDATE ai.agno_approvals -> Agno OS resumes
"""

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.database import get_pool
from . import jira_client

router = APIRouter()

JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]

# Status name your workflow uses for "not yet decided" -- adjust if you
# renamed the default "To Do" status when setting up Approved/Rejected.
PENDING_STATUS_NAME = os.environ.get("JIRA_PENDING_STATUS_NAME", "Pending")


async def fetch_tool_descriptions() -> dict[str, str]:
    """Returns {tool_name: description} from ai.tool_descriptions."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT tool_name, description FROM ai.tool_descriptions")
    return {r["tool_name"]: r["description"] for r in rows}


class ResolveRequest(BaseModel):
    decision: str  # "approved" or "rejected"


@router.get("/api/jira/approvals")
async def list_approvals(status: str | None = None):
    """Lists approval issues. status=None returns everything in the
    project; pass status="pending" to only get ones awaiting a decision."""
    jql = f'project = "{JIRA_PROJECT_KEY}" AND issuetype = Task'
    if status == "pending":
        jql += f' AND status = "{PENDING_STATUS_NAME}"'
    jql += " ORDER BY created DESC"

    issues = await jira_client.search_issues(jql, max_results=100)
    tool_descriptions = await fetch_tool_descriptions()
    return {
        "approvals": [jira_client.simplify_issue(i, tool_descriptions) for i in issues]
    }

@router.get("/api/jira/approvals/{issue_key}")
async def get_approval(issue_key: str):
    issue = await jira_client.get_issue(issue_key)
    return jira_client.simplify_issue(issue)


@router.post("/api/jira/approvals/{issue_key}/resolve")
async def resolve_approval(issue_key: str, body: ResolveRequest):
    target_status = {"approved": "Approved", "rejected": "Rejected"}.get(body.decision)
    if target_status is None:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    try:
        await jira_client.transition_issue(issue_key, target_status)
    except ValueError as e:
        # No such transition from current status -- surface it clearly
        # rather than a raw 500, this is a workflow config issue not a bug.
        raise HTTPException(status_code=409, detail=str(e))

    return {"issue_key": issue_key, "status": target_status}
