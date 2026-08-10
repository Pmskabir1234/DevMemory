"""
Unit tests for app.services.event.record_event

Covers:
- New session created on first event
- Same session reused while within timeout window
- New session created for different workspace
- New session created after an old session was summarised (completed)
- File paths deduplicated in session.files JSON list
- Event with no file_path handled gracefully
- Timezone-aware timestamps are normalised to naïve UTC
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.services.event import record_event
from app.schemas.event import EventCreate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WS_A = "C:/projects/workspace_a"
WS_B = "C:/projects/workspace_b"

NOW = datetime.now(timezone.utc)


def _make_event(
    workspace: str = WS_A,
    file_path: str | None = "src/main.py",
    event_type: str = "FileSaved",
    ts: datetime | None = None,
    metadata: dict | None = None,
) -> EventCreate:
    return EventCreate(
        event_type=event_type,
        file_path=file_path,
        workspace=workspace,
        language="python",
        timestamp=ts or NOW,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_creates_new_session_on_first_event(self, db_session):
        """First event in a workspace must create a brand-new session."""
        event = record_event(db_session, _make_event())
        assert event.id is not None
        assert event.session_id is not None

    def test_reuses_session_within_timeout(self, db_session):
        """Two events close together must land in the same session."""
        t1 = NOW
        t2 = NOW + timedelta(minutes=1)

        e1 = record_event(db_session, _make_event(ts=t1))
        e2 = record_event(db_session, _make_event(ts=t2, file_path="src/utils.py"))

        assert e1.session_id == e2.session_id

    def test_creates_new_session_for_different_workspace(self, db_session):
        """Events in different workspaces must land in different sessions."""
        e1 = record_event(db_session, _make_event(workspace=WS_A))
        e2 = record_event(db_session, _make_event(workspace=WS_B))

        assert e1.session_id != e2.session_id

    def test_creates_new_session_after_completed_session(self, db_session):
        """
        If the active session already has a summary (i.e. completed), a new event
        must NOT extend that session — it must start a fresh one.
        """
        from app.models.session import Session

        # Create first event → new session
        e1 = record_event(db_session, _make_event(ts=NOW, file_path="a.py"))
        # Mark session as completed
        session = db_session.query(Session).filter_by(id=e1.session_id).first()
        session.summary = "Done."
        db_session.commit()

        # Next event in same workspace — must get a NEW session
        e2 = record_event(db_session, _make_event(ts=NOW + timedelta(seconds=5), file_path="b.py"))
        assert e2.session_id != e1.session_id

    def test_deduplicates_files_in_session(self, db_session):
        """The same file_path recorded twice should appear only once in session.files."""
        from app.models.session import Session

        record_event(db_session, _make_event(ts=NOW, file_path="dup.py"))
        record_event(db_session, _make_event(ts=NOW + timedelta(seconds=5), file_path="dup.py"))

        sessions = db_session.query(Session).all()
        assert len(sessions) == 1
        files = json.loads(sessions[0].files)
        assert files.count("dup.py") == 1

    def test_event_without_file_path(self, db_session):
        """Events with no file_path (e.g. WorkspaceOpened) should be stored successfully."""
        e = record_event(
            db_session,
            _make_event(event_type="WorkspaceOpened", file_path=None),
        )
        assert e.id is not None
        assert e.file_path is None

    def test_timezone_aware_timestamp_normalised(self, db_session):
        """
        A timezone-aware datetime must be stored as a naïve UTC datetime
        (SQLite has no native timezone support).
        """
        aware_ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        e = record_event(db_session, _make_event(ts=aware_ts))
        assert e.timestamp.tzinfo is None
        assert e.timestamp == datetime(2026, 1, 1, 12, 0, 0)

    def test_session_duration_updated_with_multiple_events(self, db_session):
        """Session duration_seconds should grow as more events arrive."""
        from app.models.session import Session

        t1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc)

        record_event(db_session, _make_event(ts=t1))
        record_event(db_session, _make_event(ts=t2, file_path="other.py"))

        session = db_session.query(Session).first()
        assert session.duration_seconds == 300  # 5 minutes

    def test_metadata_stored_as_json(self, db_session):
        """Event metadata dict should be serialised to JSON in the database."""
        meta = {"size_bytes": 512, "lines": 20}
        e = record_event(db_session, _make_event(metadata=meta))
        stored = json.loads(e.metadata_)
        assert stored["size_bytes"] == 512
        assert stored["lines"] == 20

    def test_git_commit_event_type(self, db_session):
        """GitCommit event with hash+message metadata should be stored without errors."""
        e = record_event(
            db_session,
            _make_event(
                event_type="GitCommit",
                file_path=None,
                metadata={"commit_hash": "abc123", "message": "Initial commit"},
            ),
        )
        assert e.event_type == "GitCommit"
        meta = json.loads(e.metadata_)
        assert meta["commit_hash"] == "abc123"
