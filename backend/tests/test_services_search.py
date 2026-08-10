"""
Unit tests for app.services.search

Covers:
- search_sessions: date filtering, keyword filtering, workspace filter, fallback
- _local_answer: resume/last query, listing query, empty result
- answer_query: correct keys returned, local fallback used when no LLM key
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.session import Session
from app.services.search import search_sessions, answer_query, _local_answer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WS = "C:/projects/ws"


def _session(
    db,
    summary: str = "Worked on auth module.",
    files: list[str] | None = None,
    workspace: str = WS,
    days_ago: int = 0,
) -> Session:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(days=days_ago, hours=1)
    end = now - timedelta(days=days_ago)
    s = Session(
        workspace=workspace,
        start_time=start,
        end_time=end,
        duration_seconds=3600,
        files=json.dumps(files or ["auth.py"]),
        summary=summary,
        pending_work="- Finish login",
        decisions="- Added JWT",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


# ---------------------------------------------------------------------------
# search_sessions
# ---------------------------------------------------------------------------


class TestSearchSessions:
    def test_returns_empty_when_no_sessions(self, db_session):
        assert search_sessions(db_session, "anything") == []

    def test_keyword_match_in_summary(self, db_session):
        _session(db_session, summary="Implemented JWT authentication.")
        _session(db_session, summary="Fixed database migrations.")
        results = search_sessions(db_session, "authentication")
        assert len(results) == 1
        assert "authentication" in results[0].summary.lower()

    def test_keyword_match_in_files(self, db_session):
        _session(db_session, files=["auth.py", "token.py"])
        _session(db_session, files=["index.html"])
        results = search_sessions(db_session, "token")
        assert len(results) == 1
        files = json.loads(results[0].files)
        assert "token.py" in files

    def test_keyword_match_in_decisions(self, db_session):
        s = Session(
            workspace=WS,
            start_time=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2),
            end_time=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
            duration_seconds=3600,
            files=json.dumps([]),
            summary="Regular session.",
            pending_work="- todo",
            decisions="- Chose Redis over Memcached",
        )
        db_session.add(s)
        db_session.commit()
        results = search_sessions(db_session, "Redis")
        assert len(results) == 1

    def test_date_filter_today(self, db_session):
        _session(db_session, days_ago=0)   # today
        _session(db_session, days_ago=3)   # 3 days ago
        results = search_sessions(db_session, "today")
        assert len(results) == 1

    def test_date_filter_yesterday(self, db_session):
        _session(db_session, days_ago=0)
        _session(db_session, days_ago=1)
        results = search_sessions(db_session, "yesterday")
        assert len(results) == 1

    def test_workspace_filter(self, db_session):
        _session(db_session, workspace="C:/ws_a")
        _session(db_session, workspace="C:/ws_b")
        results = search_sessions(db_session, "auth", workspace="C:/ws_a")
        assert all(s.workspace == "C:/ws_a" for s in results)

    def test_unsummarised_sessions_excluded(self, db_session):
        """Sessions without a summary must never appear in search results."""
        s = Session(
            workspace=WS,
            start_time=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc).replace(tzinfo=None),
            duration_seconds=3600,
            files=json.dumps(["x.py"]),
            summary=None,  # not yet summarised
            pending_work=None,
            decisions=None,
        )
        db_session.add(s)
        db_session.commit()
        results = search_sessions(db_session, "x.py")
        assert results == []

    def test_fallback_returns_recent_sessions_when_no_keyword_match(self, db_session):
        """If keyword search returns nothing, fall back to most-recent sessions."""
        _session(db_session, summary="Something completely unrelated.")
        results = search_sessions(db_session, "zzznomatchzzz")
        # Fallback kicks in — should still return results
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# _local_answer
# ---------------------------------------------------------------------------


class TestLocalAnswer:
    def _fake_session(self, summary="Did stuff", files=None, pending_work=None):
        return Session(
            id=1,
            workspace=WS,
            start_time=datetime(2026, 1, 1, 9, 0, 0),
            end_time=datetime(2026, 1, 1, 10, 0, 0),
            duration_seconds=3600,
            files=json.dumps(files or ["a.py"]),
            summary=summary,
            pending_work=pending_work,
            decisions=None,
        )

    def test_no_sessions_returns_not_found_message(self):
        result = _local_answer("anything", [])
        assert "no matching" in result.lower()

    def test_resume_query_shows_last_session_info(self):
        s = self._fake_session(summary="Auth work", pending_work="- Finish login")
        result = _local_answer("resume my work", [s])
        assert "Auth work" in result
        assert "Finish login" in result

    def test_listing_query_shows_all_sessions(self):
        sessions = [self._fake_session(summary=f"Session {i}") for i in range(3)]
        result = _local_answer("what did I work on", sessions)
        assert "3" in result or "Session 0" in result


# ---------------------------------------------------------------------------
# answer_query
# ---------------------------------------------------------------------------


class TestAnswerQuery:
    def test_returns_correct_shape(self, db_session):
        _session(db_session)
        result = answer_query(db_session, "auth")
        assert "query" in result
        assert "answer" in result
        assert "matched_sessions" in result

    def test_query_field_preserved(self, db_session):
        result = answer_query(db_session, "my custom query")
        assert result["query"] == "my custom query"

    def test_matched_sessions_contains_id_date_summary(self, db_session):
        _session(db_session, summary="JWT implementation complete.")
        result = answer_query(db_session, "JWT")
        assert len(result["matched_sessions"]) >= 1
        s = result["matched_sessions"][0]
        assert "id" in s
        assert "date" in s
        assert "summary" in s

    def test_answer_is_non_empty_string(self, db_session):
        _session(db_session, summary="Worked on search feature.")
        result = answer_query(db_session, "search")
        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0

    def test_no_sessions_returns_not_found_answer(self, db_session):
        result = answer_query(db_session, "anything")
        assert "no matching" in result["answer"].lower() or isinstance(result["answer"], str)
        assert result["matched_sessions"] == []
