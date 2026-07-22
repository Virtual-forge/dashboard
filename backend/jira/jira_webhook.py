"""
Receives the callback from the Jira Automation rule when an approval issue
transitions to Approved/Rejected, and writes that back into
ai.agno_approvals -- the same kind of status write your existing
backend/main.py resolve_approval() endpoint does, just triggered by Jira
instead of your React UI. Writing the *decision* back is expected; it's
schema changes to Agno's table we're avoiding, not writes.

Mount in your existing FastAPI app:
    from app import jira_webhook
    app.include_router(jira_webhook.router)

--- Jira Automation rule setup (Project settings -> Automation) ---
Trigger:  "Issue transitioned" -> destination status is Approved OR Rejected
Action:   "Send web request"
  URL:     https://your-backend/webhooks/jira-approval
  Method:  POST
  Headers: X-Webhook-Secret: <same value as JIRA_WEBHOOK_SECRET below>
  Body (custom data):
    {
      "issue_key": "{{issue.key}}",
      "approval_id": "{{issue.fields.customfield_10050}}",
      "status": "{{issue.status.name}}",
      "resolved_by": "{{issue.assignee.displayName}}"
    }
  (swap customfield_10050 for whatever field ID you used for Approval ID)
"""

import os
import time
from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter()

load_dotenv()
JIRA_WEBHOOK_SECRET = os.environ["JIRA_WEBHOOK_SECRET"]

# Jira status names -> your internal approval status values. Confirmed
# against backend/models.py's ResolveRequest Literal["approved","rejected"].
STATUS_MAP = {
    "Approved": "approved",
    "Rejected": "rejected",
}


class JiraApprovalPayload(BaseModel):
    issue_key: str
    approval_id: str  # id is character varying, not uuid -- plain string
    status: str
    resolved_by: str | None = None


from database.database import get_pool

async def get_db_pool():
    return get_pool()

    
@router.post("/webhooks/jira-approval")
async def jira_approval_webhook(
    payload: JiraApprovalPayload,
    x_webhook_secret: str = Header(default=""),
):
    if x_webhook_secret != JIRA_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid webhook secret")

    internal_status = STATUS_MAP.get(payload.status)
    if internal_status is None:
        return {"ignored": True, "reason": f"unmapped status {payload.status!r}"}

    now_epoch = int(time.time())

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # id is varchar, no ::uuid cast needed.
        # resolved_at/updated_at are epoch bigints on this table (per
        # inspect_table.py output) -- setting both, since Agno's resume
        # check may key off either. Worth confirming against Agno's actual
        # resume/poll logic (or source) which field(s) it reads; the
        # dashboard's own resolve_approval() only set resolved_at, which
        # may or may not be the full picture.
        result = await conn.execute(
            """
            UPDATE ai.agno_approvals
            SET status = $1,
                resolved_by = $2,
                resolved_at = $3,
                updated_at = $3
            WHERE id = $4 AND status = 'pending'
            """,
            internal_status,
            payload.resolved_by or f"jira:{payload.issue_key}",
            now_epoch,
            payload.approval_id,
        )

    if result == "UPDATE 0":
        # Already resolved (e.g. raced with the old dashboard), or a bad
        # approval_id -- return 200 so Jira doesn't retry a dead delivery.
        return {"updated": False}

    return {"updated": True, "status": internal_status}
