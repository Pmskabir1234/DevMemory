"""
Unit tests for FastAPI API endpoints in app.api

Covers:
- GET /health
- POST /api/events
- GET /api/sessions
- GET /api/sessions/active
- POST /api/sessions/active/end
- GET /api/search
"""
from datetime import datetime, timezone
from unittest.mock import patch
import pytest


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_check_returns_healthy(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


# ---------------------------------------------------------------------------
# POST /api/events
# ---------------------------------------------------------------------------


class TestEventsEndpoint:
    def test_create_event_success(self, client):
        payload = {
            "event_type": "FileSaved",
            "file_path": "src/main.py",
            "workspace": "C:/projects/test_ws",
            "language": "python",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"lines": 50},
        }
        res = client.post("/api/events", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "recorded"
        assert data["id"] is not None
        assert data["session_id"] is not None

    def test_create_event_invalid_payload_returns_422(self, client):
        payload = {
            # missing event_type and workspace
            "file_path": "src/main.py",
        }
        res = client.post("/api/events", json=payload)
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/sessions & /api/sessions/active & /api/sessions/active/end
# ---------------------------------------------------------------------------


class TestSessionsEndpoints:
    def test_read_sessions_empty(self, client):
        res = client.get("/api/sessions")
        assert res.status_code == 200
        assert res.json() == []

    def test_read_sessions_with_data(self, client):
        # Create an event first to generate a session
        payload = {
            "event_type": "FileSaved",
            "file_path": "src/index.ts",
            "workspace": "C:/projects/app",
            "language": "typescript",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client.post("/api/events", json=payload)

        res = client.get("/api/sessions")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["workspace"] == "C:/projects/app"
        assert "src/index.ts" in data[0]["files"]

    def test_read_sessions_workspace_filter(self, client):
        payload_a = {
            "event_type": "FileSaved",
            "file_path": "a.py",
            "workspace": "C:/ws_a",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload_b = {
            "event_type": "FileSaved",
            "file_path": "b.py",
            "workspace": "C:/ws_b",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client.post("/api/events", json=payload_a)
        client.post("/api/events", json=payload_b)

        res = client.get("/api/sessions?workspace=C:/ws_a")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["workspace"] == "C:/ws_a"

    def test_read_active_session_none(self, client):
        res = client.get("/api/sessions/active")
        assert res.status_code == 200
        assert res.json() is None

    def test_read_active_session_exists(self, client):
        payload = {
            "event_type": "FileSaved",
            "file_path": "main.py",
            "workspace": "C:/projects/app",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client.post("/api/events", json=payload)

        res = client.get("/api/sessions/active?workspace=C:/projects/app")
        assert res.status_code == 200
        data = res.json()
        assert data is not None
        assert data["workspace"] == "C:/projects/app"

    def test_terminate_active_session_not_found(self, client):
        res = client.post("/api/sessions/active/end")
        assert res.status_code == 404
        assert res.json()["detail"] == "No active session found to end."

    def test_terminate_active_session_success(self, client):
        payload = {
            "event_type": "FileSaved",
            "file_path": "main.py",
            "workspace": "C:/projects/app",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        create_res = client.post("/api/events", json=payload)
        session_id = create_res.json()["session_id"]

        fake_summary = {
            "summary": "Worked on main.py",
            "decisions": "Created main.py",
            "pending_work": "Add tests",
        }
        with patch("app.services.session.generate_ai_summary", return_value=fake_summary):
            res = client.post("/api/sessions/active/end?workspace=C:/projects/app")

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "terminated"
        assert data["session_id"] == session_id
        assert data["summary_generated"] is True

        # Verify active session is now None
        active_res = client.get("/api/sessions/active?workspace=C:/projects/app")
        assert active_res.json() is None


# ---------------------------------------------------------------------------
# GET /api/search
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    def test_search_missing_query_returns_422(self, client):
        res = client.get("/api/search")
        assert res.status_code == 422

    def test_search_success(self, client):
        payload = {
            "event_type": "FileSaved",
            "file_path": "auth.py",
            "workspace": "C:/projects/app",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        client.post("/api/events", json=payload)

        res = client.get("/api/search?query=auth")
        assert res.status_code == 200
        data = res.json()
        assert data["query"] == "auth"
        assert "answer" in data
        assert isinstance(data["matched_sessions"], list)
