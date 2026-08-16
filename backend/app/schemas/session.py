from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, ConfigDict


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    workspace: str
    files: List[str] | None = None
    summary: str | None = None
    pending_work: str | None = None
    decisions: str | None = None


class SessionActiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    last_activity_time: datetime
    workspace: str


class SessionTerminateResponse(BaseModel):
    status: str = "terminated"
    session_id: int
    summary_generated: bool

