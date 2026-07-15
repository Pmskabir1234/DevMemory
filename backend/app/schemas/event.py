from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, Field


class EventBase(BaseModel):
    event_type: str = Field(..., description="Type of event (e.g. FileSaved, Diagnostic, GitCommit)")
    file_path: str | None = Field(None, description="Path to the file involved, relative to workspace or absolute")
    workspace: str = Field(..., description="Workspace absolute path")
    language: str | None = Field(None, description="Programming language identifier")
    timestamp: datetime = Field(..., description="Timestamp when event occurred")
    metadata: Dict[str, Any] | None = Field(None, alias="metadata", description="Additional metadata")


class EventCreate(EventBase):
    pass


class EventResponse(BaseModel):
    id: int
    status: str = "recorded"
    session_id: int | None

    class Config:
        populate_by_name = True
