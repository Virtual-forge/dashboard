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
FIELD_APPROVAL_TYPE = os.environ.get("JIRA_FIELD_APPROVAL_TYPE", "customfield_10053")

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
    """Creates a Jira issue for an approval row. Returns the issue
    key (e.g. "APR-42")."""
    # Value must match your Jira select field's option text EXACTLY
    # (case-sensitive). row["approval_type"] is already 'audit' or
    # 'required' straight from Agno -- use it directly rather than
    # reformatting, so it always matches whatever casing you used when
    # creating the field options in Jira.
    approval_type_value = row.get("approval_type") or "required"

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": JIRA_ISSUE_TYPE},
            "summary": f"Approval needed: {row['tool_name']} (agent {row.get('agent_id') or '?'})",
            "description": _adf_description(row),
            FIELD_APPROVAL_ID: str(row["id"]),
            FIELD_TOOL_NAME: row["tool_name"],
            FIELD_AGENT_ID: row.get("agent_id") or "",
            FIELD_APPROVAL_TYPE: {"value": approval_type_value},
        }
    }

    async with httpx.AsyncClient(auth=_auth, timeout=15) as client:
        resp = await client.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            print("JIRA ERROR RESPONSE BODY:", resp.text)
        resp.raise_for_status()
        return resp.json()["key"]


async def transition_issue(issue_key: str, target_status_name: str) -> None:
    """Transitions an issue to the given status by NAME (e.g. "Approved").
    Jira's create-issue API can't set status directly -- status only moves
    via workflow transitions, so this is a separate call: list the
    transitions available from the issue's current status, find the one
    whose target matches target_status_name, then fire it.

    Used for audit-type approvals: the tool already ran (no gate), so the
    Jira issue is created purely as a record and should land directly in
    an already-resolved status rather than sitting in a "needs review"
    column no human is actually going to act on.
    """
    async with httpx.AsyncClient(auth=_auth, timeout=15) as client:
        resp = await client.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions"
        )
        resp.raise_for_status()
        transitions = resp.json()["transitions"]

        match = next(
            (t for t in transitions if t["to"]["name"].lower() == target_status_name.lower()),
            None,
        )
        if match is None:
            available = [t["to"]["name"] for t in transitions]
            raise ValueError(
                f"No transition to '{target_status_name}' available from {issue_key}'s "
                f"current status. Available targets: {available}. "
                f"(Some workflows require going through intermediate statuses.)"
            )

        resp = await client.post(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
            json={"transition": {"id": match["id"]}},
        )
        resp.raise_for_status()


# Fields pulled back on every list/search call -- includes your custom
# fields so the dashboard/chatbot don't need a second round trip per issue.
_SEARCH_FIELDS = [
    "summary", "status", "assignee", "created", "updated","description",
    FIELD_APPROVAL_ID, FIELD_TOOL_NAME, FIELD_AGENT_ID, FIELD_APPROVAL_TYPE,
]


async def search_issues(jql: str, max_results: int = 50) -> list[dict]:
    """Searches issues via JQL. Uses POST /rest/api/3/search/jql --
    the old GET/POST /rest/api/3/search endpoints were fully removed by
    Atlassian in August 2025, so this is the only endpoint that still works.
    Pagination uses nextPageToken now instead of startAt; not implemented
    here since approval volume for a dashboard view is small enough that
    max_results alone is fine -- add nextPageToken looping if you ever need
    more than one page.
    """
    async with httpx.AsyncClient(auth=_auth, timeout=15) as client:
        resp = await client.post(
            f"{JIRA_BASE_URL}/rest/api/3/search/jql",
            json={"jql": jql, "maxResults": max_results, "fields": _SEARCH_FIELDS},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            print("JIRA SEARCH ERROR:", resp.text)
        resp.raise_for_status()
        return resp.json().get("issues", [])


async def get_issue(issue_key: str) -> dict:
    async with httpx.AsyncClient(auth=_auth, timeout=15) as client:
        resp = await client.get(
            f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}",
            params={"fields": ",".join(_SEARCH_FIELDS)},
        )
        if resp.status_code >= 400:
            print("JIRA GET ISSUE ERROR:", resp.text)
        resp.raise_for_status()
        return resp.json()


def _adf_to_text(adf: dict | None) -> str:
    """Inverse of _adf_description: walks the ADF doc this same client
    created and reconstructs the plain-text format the frontend parses
    (labeled lines + ```-fenced JSON blocks). Only needs to handle the
    node types _adf_description actually emits (paragraph, codeBlock,
    text) -- it's not a general ADF renderer."""
    if not adf or not isinstance(adf, dict):
        return ""

    lines = []
    for block in adf.get("content", []):
        text = "".join(
            run.get("text", "") for run in block.get("content", []) if run.get("type") == "text"
        )
        if block.get("type") == "codeBlock":
            lines.append(f"```\n{text}\n```")
        else:
            lines.append(text)
    return "\n".join(lines)

def simplify_issue(issue: dict) -> dict:
    """Flattens a raw Jira issue into the shape the dashboard/chatbot want,
    pulling values out of your custom field IDs by name."""
    fields = issue.get("fields", {})

    def _select_value(field_id):
        v = fields.get(field_id)
        return v.get("value") if isinstance(v, dict) else v

    return {
        "issue_key": issue["key"],
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "assignee": ((fields.get("assignee") or {}).get("displayName")),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "approval_id": fields.get(FIELD_APPROVAL_ID),
        "tool_name": fields.get(FIELD_TOOL_NAME),
        "agent_id": fields.get(FIELD_AGENT_ID),
        "approval_type": _select_value(FIELD_APPROVAL_TYPE),
        "description": _adf_to_text(fields.get("description")),
    }
