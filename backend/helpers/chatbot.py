"""
Backend for the dashboard's embedded chat widget. Calls external Agno Jira Agent
served as FastAPI server (uvicorn jira_agent:app --port 7777).

Mount alongside your other routers:
    from chatbot import router as chatbot_router
    app.include_router(chatbot_router)

Env vars required:
    AGNO_AGENT_URL - URL of the Agno agent FastAPI server (default: http://localhost:7777)
"""

import os
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# URL of the external Agno agent FastAPI server
AGNO_AGENT_URL = os.getenv("AGNO_AGENT_URL", "http://localhost:7777")

class ChatRequest(BaseModel):
    # Full conversation history from the frontend
    messages: list[dict]


@router.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Forward chat request to external Agno agent server.
    The Agno agent handles Jira/Confluence interactions via MCP tools.
    """
    messages = list(req.messages)
    
    # Get the last user message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    
    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Call the Agno agent's run endpoint
            # AgentOS exposes /api/agent/{agent_id}/run endpoint
            response = await client.post(
                f"{AGNO_AGENT_URL}/api/agent/jira-approval-agent/run",
                json={
                    "message": user_message,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract the agent's response
            # AgentOS returns: {"content": "...", "tool_calls": [...], ...}
            reply = data.get("content", "Sorry, I couldn't process that request.")
            
            return {"reply": reply}
            
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Agno agent server at {AGNO_AGENT_URL}. Make sure it's running (uvicorn jira_agent:app --port 7777)."
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Agno agent server error: {e.response.status_code} - {e.response.text}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling Agno agent: {str(e)}")
