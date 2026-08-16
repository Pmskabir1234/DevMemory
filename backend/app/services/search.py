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
from app.models.event import Event
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
# Intent detection
# ---------------------------------------------------------------------------

def _is_last_file_query(query: str) -> bool:
    """Detect queries asking for the most-recently modified/opened file."""
    q = query.lower()
    file_words = ("file", "files")
    action_words = ("modify", "modified", "modifi", "edit", "edited", "changed",
                    "saved", "save", "opened", "open", "last", "recent", "latest")
    has_file = any(w in q for w in file_words)
    has_action = any(w in q for w in action_words)
    return has_file and has_action


def _is_resume_query(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in ("resume", "continue", "pick up", "where did i leave", "last session"))


def _is_pending_query(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in ("pending", "todo", "to do", "unfinished", "remaining", "left"))


def _is_sessions_query(query: str) -> bool:
    q = query.lower()
    return any(w in q for w in ("sessions", "history", "worked on", "work on", "done"))


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

# "file" and "files" removed from stop-words so file-name queries still work.
# "last", "recent" removed so "last file" keeps useful terms.
_STOP_WORDS = {
    "what", "did", "i", "work", "on", "yesterday", "today", "this",
    "week", "when", "show", "me", "which",
    "do", "session", "history",
    "my", "the", "a", "an", "and", "or", "in",
    "for", "of", "to", "at", "was", "were", "had", "have", "has",
    "about", "with", "during",
}


def _extract_keywords(query: str) -> List[str]:
    # Strip punctuation except dots and slashes (to keep file paths and extensions intact)
    cleaned = query.lower().replace("?", "").replace(",", "")
    tokens = cleaned.split()
    keywords = []
    for t in tokens:
        if t in _STOP_WORDS or len(t) <= 2:
            continue
        keywords.append(t)
        # If token looks like a file path, also add just the filename stem so
        # "advanced/security.py" matches as both "advanced/security.py" and "security"
        if "/" in t or "\\" in t:
            stem = t.replace("\\", "/").split("/")[-1]
            stem_no_ext = stem.rsplit(".", 1)[0] if "." in stem else stem
            if stem_no_ext and stem_no_ext not in _STOP_WORDS and len(stem_no_ext) > 2:
                keywords.append(stem_no_ext)
        elif "." in t:
            # "security.py" → also add "security"
            stem = t.rsplit(".", 1)[0]
            if stem and stem not in _STOP_WORDS and len(stem) > 2:
                keywords.append(stem)
    return list(dict.fromkeys(keywords))  # deduplicate preserving order


# ---------------------------------------------------------------------------
# Database search — searches ALL sessions (summarised or not)
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
      1. Prefer summarised sessions; search across summary, files, decisions, pending_work.
      2. Apply date filter for temporal keywords.
      3. Apply keyword filter.
      4. If nothing matched, fall back to most-recent sessions (summarised or not).
    """
    date_start, date_end = _detect_date_filter(query)
    keywords = _extract_keywords(query)

    # ---- pass 1: summarised sessions with full-text filtering ----
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

    # ---- pass 2: if still nothing, search files column across ALL sessions ----
    if not results and keywords:
        conditions = []
        for kw in keywords:
            pat = f"%{kw}%"
            conditions.append(Session.files.ilike(pat))
        q2 = db.query(Session)
        if workspace:
            q2 = q2.filter(Session.workspace == workspace)
        q2 = q2.filter(or_(*conditions))
        results = q2.order_by(Session.end_time.desc()).limit(limit).all()

    # ---- pass 3: final fallback — most-recent sessions regardless of summary ----
    if not results:
        fb = db.query(Session)
        if workspace:
            fb = fb.filter(Session.workspace == workspace)
        results = fb.order_by(Session.end_time.desc()).limit(limit).all()

    return results


# ---------------------------------------------------------------------------
# Last-modified file helper
# ---------------------------------------------------------------------------

def _get_last_modified_file(db: DBSession, workspace: str | None = None) -> tuple[str | None, str | None]:
    """
    Return (file_path, timestamp_str) of the most-recently saved/modified file.
    Looks at the events table directly for maximum accuracy.
    """
    q = (
        db.query(Event)
        .filter(Event.file_path.isnot(None))
        .filter(Event.event_type.in_(["FileSaved", "FileOpened", "FileClosed"]))
    )
    if workspace:
        q = q.filter(Event.workspace == workspace)
    event = q.order_by(Event.timestamp.desc()).first()
    if event:
        return event.file_path, event.timestamp.strftime("%Y-%m-%d %H:%M")
    # Fall back to the files column of the most-recent session
    sq = db.query(Session)
    if workspace:
        sq = sq.filter(Session.workspace == workspace)
    session = sq.order_by(Session.end_time.desc()).first()
    if session and session.files:
        try:
            files = json.loads(session.files)
            if files:
                return files[-1], session.end_time.strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return None, None


# ---------------------------------------------------------------------------
# Local deterministic answer (no LLM)
# ---------------------------------------------------------------------------

def _local_answer(query: str, sessions: List[Session], db: DBSession | None = None) -> str:
    q = query.lower()

    # --- last-file query ---
    if _is_last_file_query(q):
        if db is not None:
            file_path, ts = _get_last_modified_file(db)
            if file_path:
                return (
                    f"The last file you modified was:\n"
                    f"  {file_path}\n"
                    f"  (at {ts})"
                )
        # Fall back to session files if no db passed
        if sessions:
            s = sessions[0]
            files_list: list[str] = []
            if s.files:
                try:
                    files_list = json.loads(s.files)
                except Exception:
                    pass
            if files_list:
                return f"The last file you modified was: {files_list[-1]} (session on {s.end_time.strftime('%Y-%m-%d %H:%M')})"
        return "No file modification events found in your history."

    # --- pending work query ---
    if _is_pending_query(q):
        lines = ["Pending work from recent sessions:\n"]
        found = False
        for s in sessions:
            if s.pending_work:
                lines.append(f"Session on {s.start_time.strftime('%Y-%m-%d')}:")
                lines.append(s.pending_work)
                lines.append("")
                found = True
        if not found:
            return "No pending work recorded in your recent sessions."
        return "\n".join(lines).strip()

    # --- resume / last session query ---
    if _is_resume_query(q) or not sessions:
        if not sessions:
            return "No sessions found in your development history yet."
        s = sessions[0]
        files_list = []
        if s.files:
            try:
                files_list = json.loads(s.files)
            except Exception:
                pass
        lines = [f"Your last session was on {s.start_time.strftime('%Y-%m-%d %H:%M')}."]
        if s.summary:
            lines.append(f"Summary: {s.summary}")
        if files_list:
            lines.append(f"Files touched: {', '.join(files_list)}")
        if s.pending_work:
            lines.append(f"Pending work:\n{s.pending_work}")
        if s.decisions:
            lines.append(f"Decisions:\n{s.decisions}")
        return "\n".join(lines)

    # --- general sessions listing ---
    lines = [f"Found {len(sessions)} matching session(s):\n"]
    for s in sessions:
        summary_text = s.summary or "(session not yet summarised)"
        lines.append(f"• {s.start_time.strftime('%Y-%m-%d %H:%M')} — {summary_text}")
        if s.files:
            try:
                fl = json.loads(s.files)
                if fl:
                    lines.append(f"  Files: {', '.join(fl)}")
            except Exception:
                pass
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

    Intent routing:
    - last-file / resume / pending queries  → always use deterministic local answer
      (these require real-time DB data; the LLM only sees historical summaries)
    - everything else  → try LLM first, fall back to local
    """
    # Import here to avoid circular imports at module load time
    from app.services.summary import generate_search_answer

    sessions = search_sessions(db, query, workspace=workspace)

    matched = [
        {
            "id": s.id,
            "date": s.start_time.strftime("%Y-%m-%d"),
            "summary": s.summary or (
                f"(active session — {len(json.loads(s.files)) if s.files else 0} file(s) touched)"
            ),
        }
        for s in sessions
    ]

    # For intent-based queries that need real-time DB data, skip the LLM entirely
    if _is_last_file_query(query) or _is_resume_query(query) or _is_pending_query(query):
        answer = _local_answer(query, sessions, db=db)
    else:
        # Try LangChain / Gemma for open-ended questions (only on summarised sessions)
        summarised = [s for s in sessions if s.summary]
        answer = generate_search_answer(query, summarised) if summarised else None
        if answer is None:
            answer = _local_answer(query, sessions, db=db)

    return {
        "query": query,
        "answer": answer,
        "matched_sessions": matched,
    }
