from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    workspace: str
    files: List[str] | None = None
    summary: str | None = None

    class Config:
        from_attributes = True


class SessionActiveResponse(BaseModel):
    id: int
    start_time: datetime
    last_activity_time: datetime
    workspace: str

    class Config:
        from_attributes = True


class SessionTerminateResponse(BaseModel):
    status: str = "terminated"
    session_id: int
    summary_generated: bool
