"""
Search service: find sessions matching a natural language query or keyword,
then optionally use an LLM to generate a conversational answer.
"""
import json
import logging
from datetime import datetime, date, timedelta, timezone
from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from app.models.session import Session
from app.services.summary import call_gemini, call_openai
from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _today_range():
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    start = datetime(today.year, today.month, today.day)
    end = start + timedelta(days=1)
    return start, end


def _yesterday_range():
    yesterday = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)).date()
    start = datetime(yesterday.year, yesterday.month, yesterday.day)
    end = start + timedelta(days=1)
    return start, end


def _week_range():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start = now - timedelta(days=7)
    return start, now


def _detect_date_filter(query: str):
    """Return (start, end) or (None, None) based on natural-language date clues."""
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

_DATE_STOP_WORDS = {
    "what", "did", "i", "work", "on", "yesterday", "today", "this",
    "week", "last", "when", "show", "me", "which", "file", "files",
    "edited", "edit", "changes", "made", "do", "sessions", "session",
    "history", "my", "recent", "the", "a", "an", "and", "or", "in",
    "for", "of", "to", "at", "was", "were", "had", "have", "has",
    "about", "with", "during", "changed", "open", "opened", "close",
    "closed", "saved", "save",
}


def _extract_keywords(query: str) -> List[str]:
    """Return meaningful keywords from the query for session text search."""
    tokens = query.lower().replace("?", "").replace(".", "").split()
    return [t for t in tokens if t not in _DATE_STOP_WORDS and len(t) > 2]


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
      1. Apply a date filter if the query contains temporal language.
      2. Apply keyword filtering against summary, files, decisions, pending_work.
      3. If no keyword match found, return the most recent sessions.
    """
    date_start, date_end = _detect_date_filter(query)
    keywords = _extract_keywords(query)

    base_query = db.query(Session).filter(Session.summary.isnot(None))

    if workspace:
        base_query = base_query.filter(Session.workspace == workspace)

    if date_start:
        base_query = base_query.filter(Session.start_time >= date_start)
    if date_end:
        base_query = base_query.filter(Session.start_time < date_end)

    # Apply keyword filters (OR across all text columns)
    if keywords:
        conditions = []
        for kw in keywords:
            like_pat = f"%{kw}%"
            conditions.append(Session.summary.ilike(like_pat))
            conditions.append(Session.files.ilike(like_pat))
            conditions.append(Session.decisions.ilike(like_pat))
            conditions.append(Session.pending_work.ilike(like_pat))
            conditions.append(Session.workspace.ilike(like_pat))
        base_query = base_query.filter(or_(*conditions))

    results = base_query.order_by(Session.start_time.desc()).limit(limit).all()

    # Fallback: if date-bounded search yielded nothing, widen to recent sessions
    if not results and (date_start or keywords):
        fallback = db.query(Session).filter(Session.summary.isnot(None))
        if workspace:
            fallback = fallback.filter(Session.workspace == workspace)
        results = fallback.order_by(Session.start_time.desc()).limit(limit).all()

    return results


# ---------------------------------------------------------------------------
# LLM answer generation
# ---------------------------------------------------------------------------

def _build_search_prompt(query: str, sessions: List[Session]) -> str:
    sessions_text = []
    for s in sessions:
        files_list = []
        if s.files:
            try:
                files_list = json.loads(s.files)
            except Exception:
                pass
        date_str = s.start_time.strftime("%Y-%m-%d %H:%M")
        sessions_text.append(
            f"[Session {s.id} — {date_str}]\n"
            f"Summary: {s.summary or 'N/A'}\n"
            f"Files: {', '.join(files_list) or 'N/A'}\n"
            f"Decisions: {s.decisions or 'N/A'}\n"
            f"Pending: {s.pending_work or 'N/A'}"
        )

    context = "\n\n---\n\n".join(sessions_text) if sessions_text else "No relevant sessions found."

    return (
        "You are a developer assistant with access to a developer's work history.\n"
        "Answer the following question concisely and helpfully, based only on the sessions provided.\n\n"
        f"Question: {query}\n\n"
        "Work History:\n"
        f"{context}\n\n"
        "Provide a direct, concise answer in plain text (not JSON). "
        "If no relevant sessions exist, say so clearly."
    )


def _local_answer(query: str, sessions: List[Session]) -> str:
    """Generate a simple deterministic answer when no LLM is configured."""
    if not sessions:
        return "No matching sessions found in your development history."

    q = query.lower()
    lines = []

    if "resume" in q or "last" in q:
        s = sessions[0]
        files_list = []
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


def answer_query(
    db: DBSession,
    query: str,
    workspace: str | None = None,
) -> dict:
    """
    Main entry point: search sessions, then generate a natural-language answer.
    Returns a dict with 'query', 'answer', and 'matched_sessions'.
    """
    sessions = search_sessions(db, query, workspace=workspace)

    # Build the matched_sessions summary list (for API response)
    matched = []
    for s in sessions:
        matched.append(
            {
                "id": s.id,
                "date": s.start_time.strftime("%Y-%m-%d"),
                "summary": s.summary or "",
            }
        )

    # Try LLM answer
    answer = None
    if sessions:
        prompt = _build_search_prompt(query, sessions)
        if settings.GEMINI_API_KEY:
            try:
                # Gemini returns JSON by default; ask for plain text here
                plain_prompt = prompt + "\n\nRespond with plain text only, no JSON."
                import urllib.request
                import urllib.error

                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                )
                payload = {
                    "contents": [{"parts": [{"text": plain_prompt}]}],
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                answer = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                logger.warning(f"Gemini search answer failed: {e}")

        if answer is None and settings.OPENAI_API_KEY:
            try:
                import urllib.request

                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                answer = resp_data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.warning(f"OpenAI search answer failed: {e}")

    if answer is None:
        answer = _local_answer(query, sessions)

    return {
        "query": query,
        "answer": answer,
        "matched_sessions": matched,
    }
