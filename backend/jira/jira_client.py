"""
Thin Jira Cloud REST API client, scoped to exactly what the approval
sync needs: read issues back for the dashboard, and transition them.

Issue *creation* happens in jira_agent.py via the python-jira library
directly (jira.create_issue(...)) -- not through this file. This client
is read/transition only.

Auth: Jira Cloud API token (basic auth: email + token), not OAuth --
this is a server-to-server call with no human in the loop at call time.

Env vars required:
    JIRA_BASE_URL      e.g. "https://your-domain.atlassian.net"
    JIRA_EMAIL         the Atlassian account email tied to the API token
    JIRA_API_TOKEN     from https://id.atlassian.com/manage-profile/security/api-tokens
    JIRA_PROJECT_KEY   e.g. "SCRUM"
    JIRA_ISSUE_TYPE    defaults to "Task"

Custom field IDs -- find yours via GET /rest/api/3/field. These match
the same env var names jira_agent.py uses, so one .env configures both.
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

FIELD_APPROVAL_ID = os.environ.get("JIRA_FIELD_APPROVAL_ID", "customfield_10044")
FIELD_TOOL_NAME = os.environ.get("JIRA_FIELD_TOOL_NAME", "customfield_10046")
FIELD_AGENT_ID = os.environ.get("JIRA_FIELD_AGENT_ID", "customfield_10045")
FIELD_APPROVAL_TYPE = os.environ.get("JIRA_FIELD_APPROVAL_TYPE", "customfield_10112")
FIELD_TOOL_CALL_ID = os.environ.get("JIRA_FIELD_TOOL_CALL_ID", "customfield_10146")
FIELD_TOOL_ARGS = os.environ.get("JIRA_FIELD_TOOL_ARGS", "customfield_10148")
FIELD_SESSION_ID = os.environ.get("JIRA_FIELD_SESSION_ID", "customfield_10145")
FIELD_RUN_ID = os.environ.get("JIRA_FIELD_RUN_ID", "customfield_10147")
FIELD_REQUESTED_BY = os.environ.get("JIRA_FIELD_REQUESTED_BY", "customfield_10181")

_auth = (JIRA_EMAIL, JIRA_API_TOKEN)


def _adf_to_text(adf: dict | None) -> str:
    """Walks a Jira ADF doc and reconstructs plain text. Only needs to
    handle paragraph/codeBlock/text nodes -- it's not a general ADF
    renderer, just enough for what Jira issues in this project contain."""
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


def _field_text(value) -> str:
    """Normalizes a custom field's value to plain text regardless of
    whether Jira configured that field as plain text (returns a str
    directly) or rich text (returns an ADF document dict) -- Tool Args
    is set up as rich text, so this unwraps it the same way _adf_to_text
    unwraps the built-in description field."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _adf_to_text(value)
    return str(value)


async def transition_issue(issue_key: str, target_status_name: str) -> None:
    """Transitions an issue to the given status by NAME (e.g. "Approved").
    Jira's API can't set status directly -- status only moves via workflow
    transitions, so this lists the transitions available from the issue's
    current status, finds the one whose target matches, then fires it.
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
    "summary", "status", "assignee", "created", "updated", "description",
    FIELD_APPROVAL_ID, FIELD_TOOL_NAME, FIELD_AGENT_ID, FIELD_APPROVAL_TYPE,
    FIELD_TOOL_ARGS, FIELD_SESSION_ID, FIELD_RUN_ID, FIELD_TOOL_CALL_ID, FIELD_REQUESTED_BY,
]


async def search_issues(jql: str, max_results: int = 50) -> list[dict]:
    """Searches issues via JQL. Uses POST /rest/api/3/search/jql --
    the old GET/POST /rest/api/3/search endpoints were fully removed by
    Atlassian in August 2025, so this is the only endpoint that still works.
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

import re

def _parse_description_sections(description: str) -> dict:
    """Splits the labeled description blob jira_agent.py writes
    (Agent:/Run:/Session:/.../Context:/Requirements:/Arguments: with
```json fenced blocks) into separate parsed fields. Falls back to
    empty values if a section is missing or fails to parse -- this is
    a lightweight extractor for a format this codebase controls, not
    a general parser."""
    sections = {"context": None, "requirements": None, "arguments": None}
    for key, label in [("context", "Context"), ("requirements", "Requirements"), ("arguments", "Arguments")]:
        match = re.search(rf"{label}:\s*```json\s*(.*?)\s*```", description, re.DOTALL)
        if match:
            try:
                sections[key] = json.loads(match.group(1))
            except json.JSONDecodeError:
                sections[key] = None
    return sections

def simplify_issue(issue: dict, tool_descriptions: dict[str, str] | None = None) -> dict:
    fields = issue.get("fields", {})
    tool_descriptions = tool_descriptions or {}

    def _select_value(field_id):
        v = fields.get(field_id)
        return v.get("value") if isinstance(v, dict) else v

    tool_name = fields.get(FIELD_TOOL_NAME)

    tool_args = fields.get(FIELD_TOOL_ARGS)
    if not isinstance(tool_args, dict):
        tool_args_text = _field_text(tool_args)
        try:
            tool_args = json.loads(tool_args_text) if tool_args_text else {}
        except json.JSONDecodeError:
            tool_args = {}

    description_text = _adf_to_text(fields.get("description"))
    parsed = _parse_description_sections(description_text)

    return {
        "issue_key": issue["key"],
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "assignee": ((fields.get("assignee") or {}).get("displayName")),
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "approval_id": fields.get(FIELD_APPROVAL_ID),
        "tool_name": tool_name,
        "tool_description": tool_descriptions.get(tool_name),
        "agent_id": fields.get(FIELD_AGENT_ID),
        "approval_type": _select_value(FIELD_APPROVAL_TYPE),
        "description": description_text,   # raw blob, still available if needed
        "requirements": parsed["requirements"],  # parsed dict, ready to use directly
        "context": parsed["context"],
        "tool_args": tool_args,
        "session_id": fields.get(FIELD_SESSION_ID),
        "run_id": fields.get(FIELD_RUN_ID),
        "tool_call_id": fields.get(FIELD_TOOL_CALL_ID),
        "requested_by": fields.get(FIELD_REQUESTED_BY),
    }
