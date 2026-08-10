"""
Unit tests for Typer CLI commands in devmem.main

Covers:
- devmem version
- devmem health (success and backend error)
- devmem history (with data and empty)
- devmem sessions (active session + completed sessions)
- devmem resume (with completed session and empty)
- devmem ask
- devmem search
"""
from unittest.mock import patch
import pytest
from typer.testing import CliRunner

from devmem.main import app

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "devmem CLI" in result.stdout


def test_health_command_success():
    with patch("devmem.client.health", return_value={"status": "healthy", "database": "connected"}):
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "healthy" in result.stdout


def test_health_command_failure():
    with patch("devmem.client.health", side_effect=ConnectionError("Backend unreachable")):
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 1
        assert "Backend unreachable" in result.stdout


def test_history_command_empty():
    with patch("devmem.client.get_sessions", return_value=[]):
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "No completed sessions found" in result.stdout


def test_history_command_with_sessions():
    fake_sessions = [
        {
            "id": 1,
            "start_time": "2026-08-10T10:00:00",
            "end_time": "2026-08-10T10:30:00",
            "duration_seconds": 1800,
            "workspace": "C:/projects/app",
            "files": ["main.py"],
            "summary": "Implemented feature A.",
            "pending_work": "Add tests",
            "decisions": "Used Typer",
        }
    ]
    with patch("devmem.client.get_sessions", return_value=fake_sessions):
        result = runner.invoke(app, ["history"])
        assert result.exit_code == 0
        assert "Showing 1 session(s)" in result.stdout
        assert "Implemented" in result.stdout


def test_sessions_command():
    fake_active = {
        "id": 2,
        "start_time": "2026-08-10T11:00:00",
        "last_activity_time": "2026-08-10T11:15:00",
        "workspace": "C:/projects/app",
    }
    with patch("devmem.client.get_sessions", return_value=[]), \
         patch("devmem.client.get_active_session", return_value=fake_active):
        result = runner.invoke(app, ["sessions"])
        assert result.exit_code == 0
        assert "Active Session" in result.stdout


def test_resume_command_success():
    fake_session = {
        "id": 1,
        "start_time": "2026-08-10T10:00:00",
        "end_time": "2026-08-10T10:30:00",
        "duration_seconds": 1800,
        "workspace": "C:/projects/app",
        "files": ["main.py"],
        "summary": "Implemented feature A.",
        "pending_work": "- Add unit tests",
        "decisions": "- Used Typer CLI",
    }
    with patch("devmem.client.get_sessions", return_value=[fake_session]):
        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 0
        assert "Implemented feature A." in result.stdout
        assert "Add unit tests" in result.stdout


def test_resume_command_empty():
    with patch("devmem.client.get_sessions", return_value=[]):
        result = runner.invoke(app, ["resume"])
        assert result.exit_code == 0
        assert "No completed sessions found" in result.stdout


def test_ask_command():
    fake_search = {
        "query": "What did I work on today?",
        "answer": "You worked on authentication and unit tests.",
        "matched_sessions": [
            {
                "id": 1,
                "date": "2026-08-10",
                "summary": "Implemented auth.",
            }
        ],
    }
    with patch("devmem.client.search", return_value=fake_search):
        result = runner.invoke(app, ["ask", "What did I work on today?"])
        assert result.exit_code == 0
        assert "You worked on authentication and unit tests." in result.stdout


def test_search_command():
    fake_search = {
        "query": "auth.py",
        "answer": "Found session matching auth.py",
        "matched_sessions": [],
    }
    with patch("devmem.client.search", return_value=fake_search):
        result = runner.invoke(app, ["search", "auth.py"])
        assert result.exit_code == 0
        assert "Found session matching auth.py" in result.stdout
