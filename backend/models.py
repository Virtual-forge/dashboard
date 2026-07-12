from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str


class ApprovalOut(BaseModel):
    id: str
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    tool_name: str
    tool_args: dict[str, Any]
    context: Optional[str] = None
    requested_by: Optional[str] = None
    status: str
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime


class ResolveRequest(BaseModel):
    decision: Literal["approved", "rejected"]
