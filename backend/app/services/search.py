"""
Search service: find sessions matching a natural language query or keyword,
then use Gemma (via LangChain + HuggingFace) to generate a conversational answer.

LLM calls are delegated to summary.generate_search_answer() so all model
config (prompt template, chain, parser) lives in one place.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from app.models.session import Session
from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _today_range():
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    start = datetime(today.year, today.month, today.day)
    return start, start + timedelta(days=1)


def _yesterday_range():
    yesterday = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)).date()
    start = datetime(yesterday.year, yesterday.month, yesterday.day)
    return start, start + timedelta(days=1)


def _week_range():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return now - timedelta(days=7), now


def _detect_date_filter(query: str):
    """Return (start, end) datetime pair or (None, None) based on temporal keywords."""
    q = query.lower()
    if "yesterday" in q:
        return _yesterday_range()
    if "today" in q or "today's" in q:
        return _today_range()
    if "this week" in q or "last week" in q or "week" in q:
        return _week_range()
    return None, None


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "what", "did", "i", "work", "on", "yesterday", "today", "this",
    "week", "last", "when", "show", "me", "which", "file", "files",
    "edited", "edit", "changes", "made", "do", "sessions", "session",
    "history", "my", "recent", "the", "a", "an", "and", "or", "in",
    "for", "of", "to", "at", "was", "were", "had", "have", "has",
    "about", "with", "during", "changed", "open", "opened", "close",
    "closed", "saved", "save",
}


def _extract_keywords(query: str) -> List[str]:
    tokens = query.lower().replace("?", "").replace(".", "").split()
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]


# ---------------------------------------------------------------------------
# Database search
# ---------------------------------------------------------------------------

def search_sessions(
    db: DBSession,
    query: str,
    workspace: str | None = None,
    limit: int = 10,
) -> List[Session]:
    """
    Return sessions relevant to *query*.

    Strategy:
      1. Apply a date filter for temporal language (today/yesterday/week).
      2. Apply ILIKE keyword filtering across all text columns.
      3. Fallback: return the most recent sessions if nothing matched.
    """
    date_start, date_end = _detect_date_filter(query)
    keywords = _extract_keywords(query)

    base = db.query(Session).filter(Session.summary.isnot(None))
    if workspace:
        base = base.filter(Session.workspace == workspace)
    if date_start:
        base = base.filter(Session.start_time >= date_start)
    if date_end:
        base = base.filter(Session.start_time < date_end)

    if keywords:
        conditions = []
        for kw in keywords:
            pat = f"%{kw}%"
            conditions.extend([
                Session.summary.ilike(pat),
                Session.files.ilike(pat),
                Session.decisions.ilike(pat),
                Session.pending_work.ilike(pat),
                Session.workspace.ilike(pat),
            ])
        base = base.filter(or_(*conditions))

    results = base.order_by(Session.start_time.desc()).limit(limit).all()

    # Widen search if date/keyword filtering returned nothing
    if not results and (date_start or keywords):
        fallback = db.query(Session).filter(Session.summary.isnot(None))
        if workspace:
            fallback = fallback.filter(Session.workspace == workspace)
        results = fallback.order_by(Session.start_time.desc()).limit(limit).all()

    return results


# ---------------------------------------------------------------------------
# Local deterministic answer (no LLM)
# ---------------------------------------------------------------------------

def _local_answer(query: str, sessions: List[Session]) -> str:
    if not sessions:
        return "No matching sessions found in your development history."

    q = query.lower()
    lines: list[str] = []

    if "resume" in q or "last" in q:
        s = sessions[0]
        files_list: list[str] = []
        if s.files:
            try:
                files_list = json.loads(s.files)
            except Exception:
                pass
        lines.append(f"Your last session was on {s.start_time.strftime('%Y-%m-%d')}.")
        lines.append(f"Summary: {s.summary}")
        if files_list:
            lines.append(f"Files: {', '.join(files_list)}")
        if s.pending_work:
            lines.append(f"Pending work:\n{s.pending_work}")
    else:
        lines.append(f"Found {len(sessions)} matching session(s):\n")
        for s in sessions:
            lines.append(
                f"• {s.start_time.strftime('%Y-%m-%d %H:%M')} — {s.summary or 'No summary'}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def answer_query(
    db: DBSession,
    query: str,
    workspace: str | None = None,
) -> dict:
    """
    Search sessions, then generate a natural-language answer via Gemma (or local fallback).
    Returns {'query', 'answer', 'matched_sessions'}.
    """
    # Import here to avoid circular imports at module load time
    from app.services.summary import generate_search_answer

    sessions = search_sessions(db, query, workspace=workspace)

    matched = [
        {
            "id": s.id,
            "date": s.start_time.strftime("%Y-%m-%d"),
            "summary": s.summary or "",
        }
        for s in sessions
    ]

    # Try LangChain / Gemma answer first
    answer = generate_search_answer(query, sessions)

    # Fall back to deterministic local answer
    if answer is None:
        answer = _local_answer(query, sessions)

    return {
        "query": query,
        "answer": answer,
        "matched_sessions": matched,
    }
