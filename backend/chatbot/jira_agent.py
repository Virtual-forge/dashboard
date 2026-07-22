import os, certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()  # requests uses this one
os.environ['CURL_CA_BUNDLE'] = certifi.where()       # some libs use this instead
import truststore
truststore.inject_into_ssl()

from fastapi import Request
from agno.agent import Agent
from agno.team import Team, TeamMode
from agno.db.postgres import PostgresDb
from agno.run.agent import RunOutput
from agno.models.nvidia import Nvidia
import time
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json
from agno.os import AgentOS
from agno.agent import RunOutput
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()


import os, certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()  # requests uses this one
os.environ['CURL_CA_BUNDLE'] = certifi.where()       # some libs use this instead

# THIS MUST BE THE VERY FIRST THING, before any other import
# that might create an httpx/aiohttp client (including agno itself)

"""Shared tool definitions — importable without agent/server side-effects."""

from agno.approval import approval
from agno.tools import tool
from agno.exceptions import StopAgentRun
from agno.run import RunContext
from agno.db.postgres import PostgresDb


def jira_approval(func):
    """Drop-in replacement for @approval — tags the tool as needing
    Jira-backed approval instead of a db-backed one."""
    wrapped = tool(requires_confirmation=True)(func)
    wrapped._jira_approval = True
    return wrapped

db = PostgresDb(
    db_url="postgresql://postgres:qaszdeszqa@localhost:5432/test_db",
    session_table="agno_sessions",
    approvals_table="agno_approvals",
)



@jira_approval
def delete_user_data(user_id: str , run_context: RunContext) -> str:
    """Permanently delete all data for a user. Requires admin approval."""
    
    return f"All data for user {user_id} has been deleted."




# ---------------------------------------------------------------------------
# DB + Agents
# ---------------------------------------------------------------------------
class JiraHitlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        is_run_endpoint = (
            request.method == "POST"
            and str(request.url.path).endswith("/runs")
        )
        if not is_run_endpoint:
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        content_type = response.headers.get("content-type", "")
        

        if "text/event-stream" in content_type:
            for line in body.decode("utf-8", errors="ignore").splitlines():
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload:
                    continue
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    continue
             
                if data.get("status", "").upper() == "PAUSED":
                  
                    import traceback

            try:
                jira.create_issue(fields={...})
            except Exception as e:
                print("JIRA ISSUE CREATION FAILED:")
                traceback.print_exc()
        elif "application/json" in content_type:
            try:
                data = json.loads(body)

                if data.get("status", "").upper() == "PAUSED":

                    try:
                        create_jira_issue_for_run(data)
                    except Exception as e:
                        print("JIRA ISSUE CREATION FAILED:", e)  # TEMP DEBUG
                 
            except json.JSONDecodeError as e:
                print("JSON DECODE FAILED:", e)  # TEMP DEBUG

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

shared_model = Nvidia(id="nvidia/nemotron-3-super-120b-a12b")

db = PostgresDb(
    db_url="postgresql://postgres:qaszdeszqa@localhost:5432/test_db",
    session_table="agno_sessions",
    approvals_table="agno_approvals",
)

executor_agent = Agent(
        id="approval-demo",
        name="Executor Agent",
        model=shared_model,     
        instructions=[
            "You are an executor agent responsible for carrying out approved actions.",
            "Before executing any tool, you must:",
            "1. Clearly STATE the action you are about to take and the specific target (e.g., database name, branch name, instance ID) - as a clear statement, not a question.",
            "2. Immediately CALL the tool - the approval mechanism will automatically prompt the user for confirmation and handle the approval flow.",
            "3. Log the action and the confirmation for audit purposes after the tool executes.",
            "If you are uncertain about any parameter, ask for clarification before proceeding.",
            "Never assume or guess the target of a destructive operation.",
            "Always prefer safety and caution.",
            "IMPORTANT: Do NOT ask the user for confirmation yourself. The approval mechanism handles confirmation automatically when you call the tool. Just state what you're doing, then call the tool immediately."
        ],
        tools=[
            delete_user_data,
            
        ],
        db=db,
        debug_mode=True,
    )
agent_os = AgentOS(
    id="approval-demo",
    agents=[executor_agent],
    db=db,
    cors_allowed_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
    ],
)

from jira import JIRA

jira = JIRA(
    server=os.environ["JIRA_BASE_URL"],
    basic_auth=(os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"]),
)
import os

FIELD_APPROVAL_ID = os.environ.get("JIRA_FIELD_APPROVAL_ID", "customfield_10044")
FIELD_TOOL_NAME = os.environ.get("JIRA_FIELD_TOOL_NAME", "customfield_10046")
FIELD_AGENT_ID = os.environ.get("JIRA_FIELD_AGENT_ID", "customfield_10045")
FIELD_APPROVAL_TYPE = os.environ.get("JIRA_FIELD_APPROVAL_TYPE", "customfield_10112")
FIELD_TOOL_CALL_ID = os.environ.get("JIRA_FIELD_TOOL_CALL_ID", "customfield_10146")
FIELD_TOOL_ARGS = os.environ.get("JIRA_FIELD_TOOL_ARGS", "customfield_10148")
FIELD_SESSION_ID = os.environ.get("JIRA_FIELD_SESSION_ID", "customfield_10145")
FIELD_RUN_ID = os.environ.get("JIRA_FIELD_RUN_ID", "customfield_10147") 
FIELD_REQUESTED_BY = os.environ.get("JIRA_FIELD_REQUESTED_BY", "customfield_10181")
def create_jira_issue_for_run(data: dict):
    # Be defensive: some run/stream payloads may omit keys or use
    # slightly different names (e.g. `active_requirements`). Use
    # .get() and fallbacks to avoid KeyError and log when required data
    # is missing.
    run_id = data.get("run_id")
    # session_id can appear under a few shapes depending on the event
    session_id = data.get("session_id") or data.get("sessionId")
    # sometimes the event contains a nested session object
    if session_id is None:
        sess = data.get("session")
        if isinstance(sess, dict):
            session_id = sess.get("id")

    agent_id = data.get("agent_id")
    requested_by = data.get("user_id", "lakehaylihamza@gmail.com")

    requirements = data.get("requirements") or data.get("active_requirements") or []

    if not session_id:
        print("create_jira_issue_for_run: missing session_id in payload; payload:", data)

    for requirement in requirements:
        # defensive access into requirement/tool_execution
        tool_exec = requirement.get("tool_execution") or requirement.get("toolExecution")
        if not tool_exec:
            continue

        if not tool_exec.get("requires_confirmation"):
            continue

        tool_call_id = tool_exec.get("tool_call_id") or tool_exec.get("toolCallId")
        tool_name = tool_exec.get("tool_name") or tool_exec.get("toolName")
        tool_args = tool_exec.get("tool_args") or tool_exec.get("toolArgs") or {}

        print("RESOLVED JIRA FIELD IDS:", {
            "APPROVAL_ID": FIELD_APPROVAL_ID,
            "TOOL_NAME": FIELD_TOOL_NAME,
            "AGENT_ID": FIELD_AGENT_ID,
            "APPROVAL_TYPE": FIELD_APPROVAL_TYPE,
            "TOOL_CALL_ID": FIELD_TOOL_CALL_ID,
            "TOOL_ARGS": FIELD_TOOL_ARGS,
            "SESSION_ID": FIELD_SESSION_ID,
            "RUN_ID": FIELD_RUN_ID,
            "REQUESTED_BY": FIELD_REQUESTED_BY,
        })

        print(f"Creating JIRA issue for run {run_id}, session {session_id}, tool {tool_name} with args {tool_args}")

        # Build description in the format expected by the frontend parser
        # Frontend expects: Agent:, Run:, Session:, Requested by (user_id):, Tool:, Context:, Requirements:, Arguments:
        # with JSON blocks for Context, Requirements, and Arguments
        import json
        description_parts = [
            f"Requirements:\n```json\n{json.dumps(requirement, indent=2)}\n```",
        ]
        description = "\n".join(description_parts)

        fields = {
            "project": {"key": "SCRUM"},
            "issuetype": {"name": "Task"},
            "summary": f"Approval: {tool_name}",
            "description": description,
            "labels": [f"run_id:{run_id}"] + ([f"session_id:{session_id}"] if session_id else []),
            FIELD_APPROVAL_ID: requirement.get("id"),
            FIELD_TOOL_NAME: tool_name,
            FIELD_AGENT_ID: agent_id,
            FIELD_APPROVAL_TYPE: tool_exec.get("approval_type", "required"),
            FIELD_TOOL_CALL_ID: tool_call_id,
            FIELD_TOOL_ARGS: json.dumps(tool_args),
            FIELD_RUN_ID: run_id,
            FIELD_REQUESTED_BY: requested_by,
        }

        # Only include session custom field if we have a value
        if session_id:
            fields[FIELD_SESSION_ID] = session_id

        jira.create_issue(fields=fields)
app = agent_os.get_app()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(JiraHitlMiddleware)
# ---------------------------------------------------------------------------
# Intercept the run endpoint to enrich approvals on every pause
# ---------------------------------------------------------------------------



if __name__ == "__main__":


    agent_os.serve(app="jira_agent:app", port=7777)