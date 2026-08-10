"""
Unit tests for app.services.summary

Focuses on generate_local_fallback (no LLM required) and the
public generate_ai_summary function when HF_API_KEY is absent.

LangChain chain paths are not exercised here because they require
live network credentials; they are covered by mocking in the
session service tests.
"""
import json
from datetime import datetime

import pytest

from app.models.event import Event
from app.models.session import Session
from app.services.summary import generate_local_fallback, generate_ai_summary, _to_bullets


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session(files: list[str] | None = None) -> Session:
    return Session(
        id=1,
        workspace="C:/projects/test",
        start_time=datetime(2026, 1, 1, 10, 0, 0),
        end_time=datetime(2026, 1, 1, 10, 5, 0),
        duration_seconds=300,
        files=json.dumps(files) if files else None,
        summary=None,
        pending_work=None,
        decisions=None,
    )


def _event(event_type: str = "FileSaved", file_path: str = "src/main.py", metadata: dict | None = None) -> Event:
    return Event(
        id=1,
        event_type=event_type,
        file_path=file_path,
        workspace="C:/projects/test",
        language="python",
        timestamp=datetime(2026, 1, 1, 10, 0, 0),
        metadata_=json.dumps(metadata) if metadata else None,
        session_id=1,
    )


# ---------------------------------------------------------------------------
# _to_bullets
# ---------------------------------------------------------------------------


class TestToBullets:
    def test_list_to_bullets(self):
        assert _to_bullets(["a", "b"]) == "- a\n- b"

    def test_empty_list(self):
        assert _to_bullets([]) == ""

    def test_string_passthrough(self):
        assert _to_bullets("already a string") == "already a string"

    def test_skips_blank_items(self):
        assert _to_bullets(["a", "  ", "b"]) == "- a\n- b"


# ---------------------------------------------------------------------------
# generate_local_fallback
# ---------------------------------------------------------------------------


class TestGenerateLocalFallback:
    def test_returns_dict_with_required_keys(self):
        result = generate_local_fallback(_session(), [])
        assert "summary" in result
        assert "decisions" in result
        assert "pending_work" in result

    def test_summary_mentions_files_when_present(self):
        result = generate_local_fallback(_session(["auth.py", "utils.py"]), [])
        assert "auth.py" in result["summary"] or "utils.py" in result["summary"]

    def test_summary_with_no_files(self):
        result = generate_local_fallback(_session([]), [])
        assert "no modified files" in result["summary"].lower() or "no files" in result["summary"].lower()

    def test_git_commit_message_included_in_summary(self):
        events = [
            _event("GitCommit", file_path=None, metadata={"commit_hash": "abc123", "message": "feat: add login"}),
        ]
        result = generate_local_fallback(_session(), events)
        assert "feat: add login" in result["summary"]
        assert "feat: add login" in result["decisions"]

    def test_diagnostic_event_added_to_pending_work(self):
        events = [
            _event("Diagnostic", "src/auth.py", {"severity": "Error", "message": "undefined variable"}),
        ]
        result = generate_local_fallback(_session(["src/auth.py"]), events)
        assert "undefined variable" in result["pending_work"]

    def test_decisions_is_string(self):
        result = generate_local_fallback(_session(["a.py"]), [])
        assert isinstance(result["decisions"], str)

    def test_pending_work_is_string(self):
        result = generate_local_fallback(_session(["a.py"]), [])
        assert isinstance(result["pending_work"], str)

    def test_multiple_commits_all_in_decisions(self):
        events = [
            _event("GitCommit", None, {"message": "commit A"}),
            _event("GitCommit", None, {"message": "commit B"}),
        ]
        result = generate_local_fallback(_session(), events)
        assert "commit A" in result["decisions"]
        assert "commit B" in result["decisions"]


# ---------------------------------------------------------------------------
# generate_ai_summary  (no HF_API_KEY → local fallback path)
# ---------------------------------------------------------------------------


class TestGenerateAiSummaryFallback:
    def test_uses_local_fallback_when_no_api_key(self, monkeypatch):
        """Without an API key the function must return a valid local summary."""
        monkeypatch.setattr("app.services.summary.settings.HF_API_KEY", None)
        result = generate_ai_summary(_session(["main.py"]), [_event()])
        assert result["summary"]
        assert result["decisions"]
        assert result["pending_work"]

    def test_returns_non_empty_strings(self, monkeypatch):
        monkeypatch.setattr("app.services.summary.settings.HF_API_KEY", None)
        result = generate_ai_summary(_session(["a.py", "b.py"]), [])
        for key in ("summary", "decisions", "pending_work"):
            assert isinstance(result[key], str)
            assert len(result[key]) > 0
