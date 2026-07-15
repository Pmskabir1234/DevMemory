import json
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.models.session import Session
from app.models.event import Event
from app.services.summary import generate_ai_summary



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
        # Retrieve all events associated with this session ordered chronologically
        events = db.query(Event).filter(Event.session_id == session.id).order_by(Event.timestamp.asc()).all()

        # Generate summary (AI or fallback)
        ai_data = generate_ai_summary(session, events)
        session.summary = ai_data.get("summary")
        session.pending_work = ai_data.get("pending_work")
        session.decisions = ai_data.get("decisions")

        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    return None
