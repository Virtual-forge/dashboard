"""
Agno Agent for Jira/Confluence integration served as FastAPI server.
Run with: uvicorn jira_agent:app --port 7777
"""
import os
from fastapi import FastAPI
from agno.agent import Agent
from agno.models.nvidia import Nvidia
from agno.tools.mcp import MCPTools
from agno.db.postgres import PostgresDb
from agno.os import AgentOS
from dotenv import load_dotenv

load_dotenv()

# Database URL for PostgresDb (sessions/approvals storage)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:qaszdeszqa@localhost:5432/test_db")

# Nvidia API Key for Nemotron model
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# Jira/Confluence MCP configuration
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "https://lakehaylihamza.atlassian.net/").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "lakehaylihamza@gmail.com")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Initialize PostgresDb for agent sessions and approvals storage
db = PostgresDb(
    db_url=DATABASE_URL,
    session_table="agno_sessions",
    approvals_table="agno_approvals",
)



# Initialize MCPTools for Jira/Confluence via mcp-atlassian
jira_mcp = MCPTools(
    command="uvx mcp-atlassian",
    env={
        "JIRA_URL": JIRA_BASE_URL,
        "JIRA_USERNAME": JIRA_EMAIL,
        "JIRA_API_TOKEN": JIRA_API_TOKEN,

    },
)

# Initialize Nvidia Nemotron-3-Super-120b model
shared_model = Nvidia(
    id="nvidia/nemotron-3-super-120b-a12b",
    api_key=NVIDIA_API_KEY,
)

# Create the Jira Agent with Agno
jira_agent = Agent(
    name="Jira Approval Agent",
    model=shared_model,
    tools=[jira_mcp],
    db=db,
    instructions=[
        "You are a Jira Approval Assistant that helps users manage approval requests in Jira.",
        "You have access to Jira and Confluence via MCP tools.",
        "You can search for issues, get issue details, transition issues, add comments, and more.",
        "When users ask about approvals, use the Jira MCP tools to find and manage approval issues.",
        "Approval issues typically have issue type 'Task' and custom fields for approval tracking.",
        "Always use the Jira issue key (e.g., APR-123) when referencing issues.",
        "Be helpful and concise in your responses.",
    ],
    markdown=True,
)

# Create AgentOS and get FastAPI app
agent_os = AgentOS(
    id="jira-approval-agent",
    agents=[jira_agent],
    db=db,
)

# This is the FastAPI app that uvicorn will serve
app = agent_os.get_app()


if __name__ == "__main__":
    agent_os.serve(app="jira_agent:app", reload=True)