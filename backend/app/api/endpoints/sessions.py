import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.session import (
    SessionActiveResponse,
    SessionResponse,
    SessionTerminateResponse,
)
from app.services.session import end_active_session, get_active_session, get_sessions

router = APIRouter()


@router.get("", response_model=List[SessionResponse])
def read_sessions(
    workspace: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    db_sessions = get_sessions(db, workspace=workspace, limit=limit, offset=offset)

    response = []
    for s in db_sessions:
        files_list = []
        if s.files:
            try:
                files_list = json.loads(s.files)
            except Exception:
                files_list = []
        response.append(
            SessionResponse(
                id=s.id,
                start_time=s.start_time,
                end_time=s.end_time,
                duration_seconds=s.duration_seconds,
                workspace=s.workspace,
                files=files_list,
                summary=s.summary,
            )
        )
    return response


@router.get("/active", response_model=SessionActiveResponse | None)
def read_active_session(
    workspace: str | None = None, db: Session = Depends(get_db)
):
    active = get_active_session(db, workspace=workspace)
    if not active:
        return None
    return SessionActiveResponse(
        id=active.id,
        start_time=active.start_time,
        last_activity_time=active.end_time,
        workspace=active.workspace,
    )


@router.post("/active/end", response_model=SessionTerminateResponse)
def terminate_active_session(
    workspace: str | None = None, db: Session = Depends(get_db)
):
    ended = end_active_session(db, workspace=workspace)
    if not ended:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found to end.",
        )
    return SessionTerminateResponse(
        status="terminated", session_id=ended.id, summary_generated=True
    )
