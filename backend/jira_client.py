"""
Thin Jira Cloud REST API client, scoped to exactly what the approval
sync needs: create an issue.

Auth: Jira Cloud API token (basic auth: email + token), not OAuth --
this is a server-to-server call with no human in the loop at call time.

Env vars required:
    JIRA_BASE_URL      e.g. "https://your-domain.atlassian.net"
    JIRA_EMAIL         the Atlassian account email tied to the API token
    JIRA_API_TOKEN     from https://id.atlassian.com/manage-profile/security/api-tokens
    JIRA_PROJECT_KEY   e.g. "APR"
    JIRA_ISSUE_TYPE    defaults to "Task"

Custom field IDs -- find yours via GET /rest/api/3/field.
"""

import json
import os
from dotenv import load_dotenv
load_dotenv()
import httpx

JIRA_BASE_URL = os.environ["JIRA_BASE_URL"].rstrip("/")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]
JIRA_ISSUE_TYPE = os.environ.get("JIRA_ISSUE_TYPE", "Task")

FIELD_APPROVAL_ID = os.environ.get("JIRA_FIELD_APPROVAL_ID", "customfield_10050")
FIELD_TOOL_NAME = os.environ.get("JIRA_FIELD_TOOL_NAME", "customfield_10051")
FIELD_AGENT_ID = os.environ.get("JIRA_FIELD_AGENT_ID", "customfield_10052")

_auth = (JIRA_EMAIL, JIRA_API_TOKEN)


def _jsonify(value):
    """context/requirements/tool_args come back from Postgres as jsonb --
    asyncpg gives you either a str (needs json.loads) or an already-parsed
    dict/list depending on codec setup. Normalize either way."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _adf_description(row: dict) -> dict:
    """Jira Cloud requires descriptions in Atlassian Document Format (ADF).
    row is a dict of ai.agno_approvals columns, plus an optional
    'tool_description' pulled from your (public schema) tool_descriptions table."""
    context = _jsonify(row.get("context"))
    requirements = _jsonify(row.get("requirements"))
    tool_args = _jsonify(row.get("tool_args")) or {}

    lines = [
        f"Agent: {row.get('agent_id') or '(none)'}",
        f"Team: {row.get('team_id') or '(none)'}   Workflow: {row.get('workflow_id') or '(none)'}",
        f"Run: {row.get('run_id') or '(none)'}   Session: {row.get('session_id') or '(none)'}",
        f"Requested by (user_id): {row.get('user_id') or '(unknown)'}",
        f"Source: {row.get('source_type') or '?'} / {row.get('source_name') or '?'}",
        f"Approval type: {row.get('approval_type') or '?'}   Pause type: {row.get('pause_type') or '?'}",
    ]
    if row.get("tool_description"):
        lines.append(f"Tool: {row['tool_name']} -- {row['tool_description']}")
    else:
        lines.append(f"Tool: {row['tool_name']}")

    blocks = [
        {"type": "paragraph", "content": [{"type": "text", "text": "\n".join(lines)}]}
    ]

    if context:
        blocks.append({"type": "paragraph", "content": [{"type": "text", "text": "Context:"}]})
        blocks.append({"type": "codeBlock", "content": [{"type": "text", "text": json.dumps(context, indent=2)}]})

    if requirements:
        blocks.append({"type": "paragraph", "content": [{"type": "text", "text": "Requirements:"}]})
        blocks.append({"type": "codeBlock", "content": [{"type": "text", "text": json.dumps(requirements, indent=2)}]})

    blocks.append({"type": "paragraph", "content": [{"type": "text", "text": "Arguments:"}]})
    blocks.append({"type": "codeBlock", "content": [{"type": "text", "text": json.dumps(tool_args, indent=2)}]})

    return {"type": "doc", "version": 1, "content": blocks}


async def create_approval_issue(row: dict) -> str:
    """Creates a Jira issue for a pending approval row. Returns the issue
    key (e.g. "APR-42")."""
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": JIRA_ISSUE_TYPE},
            "summary": f"Approval needed: {row['tool_name']} (agent {row.get('agent_id') or '?'})",
            "description": _adf_description(row),
            FIELD_APPROVAL_ID: str(row["id"]),
            FIELD_TOOL_NAME: row["tool_name"],
            FIELD_AGENT_ID: row.get("agent_id") or "",
        }
    }

    async with httpx.AsyncClient(auth=_auth, timeout=15) as client:
        resp = await client.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        print("JIRA ERROR RESPONSE BODY:", resp.text)
        resp.raise_for_status()
        return resp.json()["key"]
