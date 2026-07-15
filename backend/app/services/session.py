import json
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.models.session import Session


def get_sessions(
    db: DBSession, workspace: str | None = None, limit: int = 20, offset: int = 0
) -> List[Session]:
    query = db.query(Session)
    if workspace:
        query = query.filter(Session.workspace == workspace)
    return query.order_by(Session.start_time.desc()).limit(limit).offset(offset).all()


def get_active_session(db: DBSession, workspace: str | None = None) -> Session | None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    timeout_seconds = settings.SESSION_TIMEOUT_MINUTES * 60

    query = db.query(Session).filter(Session.summary.is_(None))
    if workspace:
        query = query.filter(Session.workspace == workspace)

    session = query.order_by(Session.end_time.desc()).first()
    if session:
        if (now - session.end_time).total_seconds() <= timeout_seconds:
            return session
    return None


def end_active_session(db: DBSession, workspace: str | None = None) -> Session | None:
    session = get_active_session(db, workspace)
    if session:
        # Generate summary
        # For now, we use a simple placeholder. In Phase 6, we'll hook this up to an LLM service.
        # But we also list the files involved.
        files_list = []
        if session.files:
            try:
                files_list = json.loads(session.files)
            except Exception:
                files_list = []

        files_str = ", ".join(files_list) if files_list else "no files"
        session.summary = f"Completed development session. Touched: {files_str}."
        session.pending_work = "No pending work recorded."
        session.decisions = "No major decisions recorded."
        
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    return None
