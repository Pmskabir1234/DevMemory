"""
Unit tests for app.services.session

Covers:
- get_sessions: returns all sessions, respects workspace filter
- get_active_session: returns active session within timeout, None when expired/none
- end_active_session: summarises and marks session completed, returns None when no active
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.session import Session
from app.models.event import Event
from app.services.session import get_sessions, get_active_session, end_active_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WS_A = "C:/projects/workspace_a"
WS_B = "C:/projects/workspace_b"


def _make_session(
    db,
    workspace: str = WS_A,
    summary: str | None = None,
    minutes_ago: int = 0,
) -> Session:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(minutes=minutes_ago + 5)
    end = now - timedelta(minutes=minutes_ago)
    s = Session(
        workspace=workspace,
        start_time=start,
        end_time=end,
        duration_seconds=300,
        files=json.dumps(["src/main.py"]),
        summary=summary,
        pending_work=None,
        decisions=None,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_event(db, session: Session) -> Event:
    e = Event(
        event_type="FileSaved",
        file_path="src/main.py",
        workspace=session.workspace,
        language="python",
        timestamp=session.start_time,
        metadata_=None,
        session_id=session.id,
    )
    db.add(e)
    db.commit()
    return e


# ---------------------------------------------------------------------------
# get_sessions
# ---------------------------------------------------------------------------


class TestGetSessions:
    def test_returns_empty_when_no_sessions(self, db_session):
        assert get_sessions(db_session) == []

    def test_returns_all_sessions(self, db_session):
        _make_session(db_session, workspace=WS_A)
        _make_session(db_session, workspace=WS_B)
        result = get_sessions(db_session)
        assert len(result) == 2

    def test_filters_by_workspace(self, db_session):
        _make_session(db_session, workspace=WS_A)
        _make_session(db_session, workspace=WS_B)
        result = get_sessions(db_session, workspace=WS_A)
        assert len(result) == 1
        assert result[0].workspace == WS_A

    def test_respects_limit_and_offset(self, db_session):
        for _ in range(5):
            _make_session(db_session)
        assert len(get_sessions(db_session, limit=2)) == 2
        assert len(get_sessions(db_session, limit=2, offset=3)) == 2

    def test_ordered_most_recent_first(self, db_session):
        s_old = _make_session(db_session, minutes_ago=60)
        s_new = _make_session(db_session, minutes_ago=5)
        result = get_sessions(db_session)
        assert result[0].id == s_new.id
        assert result[1].id == s_old.id


# ---------------------------------------------------------------------------
# get_active_session
# ---------------------------------------------------------------------------


class TestGetActiveSession:
    def test_returns_none_when_no_sessions(self, db_session):
        assert get_active_session(db_session) is None

    def test_returns_active_unsummarised_session(self, db_session):
        s = _make_session(db_session, summary=None, minutes_ago=0)
        result = get_active_session(db_session)
        assert result is not None
        assert result.id == s.id

    def test_returns_none_for_completed_session(self, db_session):
        _make_session(db_session, summary="Done.", minutes_ago=0)
        assert get_active_session(db_session) is None

    def test_returns_none_when_session_timed_out(self, db_session):
        # Session whose last event was 20 minutes ago → beyond the 15-min timeout
        _make_session(db_session, summary=None, minutes_ago=20)
        assert get_active_session(db_session) is None

    def test_filters_by_workspace(self, db_session):
        _make_session(db_session, workspace=WS_A, summary=None, minutes_ago=0)
        _make_session(db_session, workspace=WS_B, summary=None, minutes_ago=0)
        result = get_active_session(db_session, workspace=WS_A)
        assert result is not None
        assert result.workspace == WS_A


# ---------------------------------------------------------------------------
# end_active_session
# ---------------------------------------------------------------------------


class TestEndActiveSession:
    def test_returns_none_when_no_active_session(self, db_session):
        assert end_active_session(db_session) is None

    def test_sets_summary_on_session(self, db_session):
        s = _make_session(db_session, summary=None, minutes_ago=0)
        _make_event(db_session, s)

        # Patch the AI summary to return a deterministic result
        fake_summary = {
            "summary": "Worked on main.py",
            "decisions": "- Saved main.py",
            "pending_work": "- Continue on main.py",
        }
        with patch("app.services.session.generate_ai_summary", return_value=fake_summary):
            ended = end_active_session(db_session)

        assert ended is not None
        assert ended.summary == "Worked on main.py"
        assert ended.decisions == "- Saved main.py"
        assert ended.pending_work == "- Continue on main.py"

    def test_session_no_longer_active_after_end(self, db_session):
        s = _make_session(db_session, summary=None, minutes_ago=0)
        _make_event(db_session, s)

        fake_summary = {"summary": "Done", "decisions": "- x", "pending_work": "- y"}
        with patch("app.services.session.generate_ai_summary", return_value=fake_summary):
            end_active_session(db_session)

        # After ending, get_active_session should return None
        assert get_active_session(db_session) is None

    def test_filters_by_workspace(self, db_session):
        _make_session(db_session, workspace=WS_A, summary=None, minutes_ago=0)
        _make_session(db_session, workspace=WS_B, summary=None, minutes_ago=0)

        fake_summary = {"summary": "Done", "decisions": "- x", "pending_work": "- y"}
        with patch("app.services.session.generate_ai_summary", return_value=fake_summary):
            ended = end_active_session(db_session, workspace=WS_A)

        assert ended is not None
        assert ended.workspace == WS_A
        # WS_B session still active
        assert get_active_session(db_session, workspace=WS_B) is not None
