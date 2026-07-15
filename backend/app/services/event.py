import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.models.event import Event
from app.models.session import Session
from app.schemas.event import EventCreate


def record_event(db: DBSession, event_in: EventCreate) -> Event:
    # Ensure timestamp is a naive UTC datetime
    event_time = event_in.timestamp
    if event_time.tzinfo is not None:
        event_time = event_time.astimezone(timezone.utc).replace(tzinfo=None)

    # 1. Look for an active session in the same workspace that hasn't been completed/summarized yet
    active_session = (
        db.query(Session)
        .filter(Session.workspace == event_in.workspace)
        .filter(Session.summary.is_(None))
        .order_by(Session.end_time.desc())
        .first()
    )

    session = None
    if active_session:
        # Calculate time gap in seconds between event and active session
        time_diff = (event_time - active_session.end_time).total_seconds()
        timeout_seconds = settings.SESSION_TIMEOUT_MINUTES * 60

        if 0 <= time_diff <= timeout_seconds:
            # Event is within the inactivity window after the session end
            session = active_session
        elif active_session.start_time <= event_time <= active_session.end_time:
            # Event timestamp is inside the existing session window
            session = active_session
        elif time_diff < 0 and (active_session.start_time - event_time).total_seconds() <= timeout_seconds:
            # Event is slightly before the session start, we can extend the start time
            session = active_session
            session.start_time = event_time
            session.duration_seconds = int((session.end_time - session.start_time).total_seconds())

    # 2. If no active session found, create a new one
    if not session:
        files_list = [event_in.file_path] if event_in.file_path else []
        session = Session(
            start_time=event_time,
            end_time=event_time,
            duration_seconds=0,
            workspace=event_in.workspace,
            files=json.dumps(files_list),
            summary=None,
            pending_work=None,
            decisions=None,
        )
        db.add(session)
        db.flush()  # Flush to get the session ID
    else:
        # Update existing session
        session.end_time = max(session.end_time, event_time)
        session.start_time = min(session.start_time, event_time)
        session.duration_seconds = int((session.end_time - session.start_time).total_seconds())

        # Update files touched list
        files_list = []
        if session.files:
            try:
                files_list = json.loads(session.files)
            except Exception:
                files_list = []

        if event_in.file_path and event_in.file_path not in files_list:
            files_list.append(event_in.file_path)
            session.files = json.dumps(files_list)

        db.add(session)

    # 3. Create the event
    metadata_str = json.dumps(event_in.metadata) if event_in.metadata is not None else None
    db_event = Event(
        event_type=event_in.event_type,
        file_path=event_in.file_path,
        workspace=event_in.workspace,
        language=event_in.language,
        timestamp=event_time,
        metadata_=metadata_str,
        session_id=session.id,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return db_event
