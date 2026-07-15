"""
Session summary service.

Primary LLM  : Google Gemma (HuggingFace Inference API)
Framework    : LangChain — ChatPromptTemplate | ChatHuggingFace | JsonOutputParser / StrOutputParser
Fallback     : Deterministic local summary (no API required)

Chains
------
_summary_chain()  →  prompt | chat_model | JsonOutputParser(pydantic=SessionSummary)
_search_chain()   →  prompt | chat_model | StrOutputParser

Both chains are built lazily (once per process) so the HuggingFaceEndpoint is
not instantiated until the first request that actually needs the LLM.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import List

from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.event import Event
from app.models.session import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output schema  (LangChain JsonOutputParser uses this for structured output)
# ---------------------------------------------------------------------------

class SessionSummaryOutput(BaseModel):
    """Schema that Gemma must conform to when summarising a session."""

    summary: str = Field(description="One-sentence summary of what was worked on.")
    decisions: List[str] = Field(description="Key decisions or actions taken during the session.")
    pending_work: List[str] = Field(description="Unfinished tasks or next steps remaining.")


# ---------------------------------------------------------------------------
# Lazy chain builders  (built once, reused across requests)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _build_chat_model():
    """Instantiate ChatHuggingFace wrapping HuggingFaceEndpoint (Gemma). Cached."""
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

    llm = HuggingFaceEndpoint(
        repo_id=settings.HF_MODEL_ID,
        task="text-generation",
        max_new_tokens=1024,
        temperature=0.2,
        repetition_penalty=1.05,
        huggingfacehub_api_token=settings.HF_API_KEY,
    )
    return ChatHuggingFace(llm=llm, verbose=False)


@lru_cache(maxsize=1)
def _summary_chain():
    """
    LCEL chain for session summarisation.

    Chain:  ChatPromptTemplate | ChatHuggingFace | JsonOutputParser
    Output: dict with keys summary, decisions, pending_work
    """
    from langchain_core.output_parsers import JsonOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    parser = JsonOutputParser(pydantic_object=SessionSummaryOutput)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert developer activity analyzer. "
            "Follow the output format instructions precisely.\n\n"
            "{format_instructions}",
        ),
        (
            "human",
            "Analyse the development session below and return a structured JSON summary.\n\n"
            "Workspace : {workspace}\n"
            "Duration  : {duration_seconds} seconds\n"
            "Files     : {files}\n\n"
            "Events (chronological):\n{events}",
        ),
    ]).partial(format_instructions=parser.get_format_instructions())

    return prompt | _build_chat_model() | parser


@lru_cache(maxsize=1)
def _search_chain():
    """
    LCEL chain for natural-language search answers.

    Chain:  ChatPromptTemplate | ChatHuggingFace | StrOutputParser
    Output: plain-text answer string
    """
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a developer assistant with access to a developer's work history. "
            "Answer questions concisely and helpfully using only the sessions provided. "
            "Respond in plain text — no JSON, no markdown.",
        ),
        (
            "human",
            "Question: {query}\n\nWork History:\n{context}",
        ),
    ])

    return prompt | _build_chat_model() | StrOutputParser()


# ---------------------------------------------------------------------------
# Input formatters
# ---------------------------------------------------------------------------

def _format_events(events: list[Event]) -> str:
    lines: list[str] = []
    for event in events:
        time_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{time_str}] {event.event_type}"
        if event.file_path:
            line += f" — {event.file_path}"
        if event.metadata_:
            try:
                meta = json.loads(event.metadata_)
                useful = {k: meta[k] for k in ("message", "severity", "commit_hash") if k in meta}
                if useful:
                    line += f"  {json.dumps(useful)}"
            except Exception:
                pass
        lines.append(line)
    return "\n".join(lines) if lines else "(no events)"


def _format_session_context(sessions: list[Session]) -> str:
    parts: list[str] = []
    for s in sessions:
        files_list: list[str] = []
        if s.files:
            try:
                files_list = json.loads(s.files)
            except Exception:
                pass
        parts.append(
            f"[Session {s.id} — {s.start_time.strftime('%Y-%m-%d %H:%M')}]\n"
            f"Summary  : {s.summary or 'N/A'}\n"
            f"Files    : {', '.join(files_list) or 'N/A'}\n"
            f"Decisions: {s.decisions or 'N/A'}\n"
            f"Pending  : {s.pending_work or 'N/A'}"
        )
    return "\n\n---\n\n".join(parts) if parts else "No relevant sessions found."


# ---------------------------------------------------------------------------
# Output normaliser  (list[str] → bullet string)
# ---------------------------------------------------------------------------

def _to_bullets(val) -> str:
    if isinstance(val, list):
        return "\n".join(f"- {item}" for item in val if str(item).strip())
    return str(val).strip()


# ---------------------------------------------------------------------------
# Local deterministic fallback  (no API required)
# ---------------------------------------------------------------------------

def generate_local_fallback(session: Session, events: list[Event]) -> dict:
    """Build a deterministic summary from raw event data without any LLM call."""
    files_list: list[str] = []
    if session.files:
        try:
            files_list = json.loads(session.files)
        except Exception:
            pass

    files_str = ", ".join(files_list) if files_list else "no files"
    commit_messages: list[str] = []
    diagnostics: list[str] = []

    for event in events:
        if event.event_type == "GitCommit" and event.metadata_:
            try:
                msg = json.loads(event.metadata_).get("message")
                if msg:
                    commit_messages.append(msg)
            except Exception:
                pass
        elif event.event_type == "Diagnostic" and event.metadata_:
            try:
                meta = json.loads(event.metadata_)
                sev = meta.get("severity", "Warning")
                msg = meta.get("message")
                if msg:
                    diagnostics.append(f"[{sev}] {event.file_path}: {msg}")
            except Exception:
                pass

    summary = (
        f"Worked on development task. Commits: {'; '.join(commit_messages)}."
        if commit_messages
        else (
            f"Completed development session. Touched: {files_str}."
            if files_list
            else "Completed development session with no modified files."
        )
    )

    decisions = (
        [f"Committed: {m}" for m in commit_messages]
        or [f"Modified and saved {f}" for f in files_list]
        or ["No major decisions recorded."]
    )
    pending = (
        [f"Resolve diagnostic: {d}" for d in diagnostics]
        or ([f"Continue working on changes in: {files_str}"] if files_list else [])
        or ["Verify changes and plan next steps."]
    )

    return {
        "summary": summary,
        "decisions": _to_bullets(decisions),
        "pending_work": _to_bullets(pending),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_ai_summary(session: Session, events: list[Event]) -> dict:
    """
    Generate a session summary.

    Chain: ChatPromptTemplate | ChatHuggingFace | JsonOutputParser(SessionSummaryOutput)

    Falls back to generate_local_fallback() if the key is missing or the chain fails.
    """
    if not settings.HF_API_KEY:
        logger.info("Session %s: no HF_API_KEY — using local fallback.", session.id)
        return generate_local_fallback(session, events)

    files_list: list[str] = []
    if session.files:
        try:
            files_list = json.loads(session.files)
        except Exception:
            pass

    try:
        chain = _summary_chain()
        result: dict = chain.invoke({
            "workspace": session.workspace,
            "duration_seconds": session.duration_seconds,
            "files": files_list,
            "events": _format_events(events),
        })
        logger.info("Session %s: Gemma summary generated via LangChain.", session.id)
        return {
            "summary": result.get("summary", "No summary generated."),
            "decisions": _to_bullets(result.get("decisions", [])) or "No major decisions recorded.",
            "pending_work": _to_bullets(result.get("pending_work", [])) or "No pending work recorded.",
        }
    except Exception as exc:
        logger.warning(
            "Session %s: LangChain/Gemma summary failed (%s). Using local fallback.",
            session.id,
            exc,
        )
        return generate_local_fallback(session, events)


def generate_search_answer(query: str, sessions: list[Session]) -> str | None:
    """
    Generate a natural-language answer for a search query.

    Chain: ChatPromptTemplate | ChatHuggingFace | StrOutputParser

    Returns None if the key is missing or the chain fails (caller uses local fallback).
    """
    if not settings.HF_API_KEY or not sessions:
        return None

    try:
        chain = _search_chain()
        answer: str = chain.invoke({
            "query": query,
            "context": _format_session_context(sessions),
        })
        logger.info("Search query answered via LangChain/Gemma.")
        return answer.strip()
    except Exception as exc:
        logger.warning("LangChain search answer failed (%s). Caller will use local fallback.", exc)
        return None
