import json
import urllib.request
import urllib.error
import logging
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.models.session import Session
from app.models.event import Event

logger = logging.getLogger(__name__)


def generate_local_fallback(session: Session, events: list[Event]) -> dict:
    files_list = []
    if session.files:
        try:
            files_list = json.loads(session.files)
        except Exception:
            files_list = []

    files_str = ", ".join(files_list) if files_list else "no files"

    # Analyze events for fallback summary
    commit_messages = []
    diagnostics = []
    for event in events:
        if event.event_type == "GitCommit" and event.metadata_:
            try:
                meta = json.loads(event.metadata_)
                msg = meta.get("message")
                if msg:
                    commit_messages.append(msg)
            except Exception:
                pass
        elif event.event_type == "Diagnostic" and event.metadata_:
            try:
                meta = json.loads(event.metadata_)
                severity = meta.get("severity", "Warning")
                msg = meta.get("message")
                if msg:
                    diagnostics.append(f"[{severity}] {event.file_path}: {msg}")
            except Exception:
                pass

    if commit_messages:
        summary = f"Worked on development task. Commits: {'; '.join(commit_messages)}."
    elif files_list:
        summary = f"Completed development session. Touched: {files_str}."
    else:
        summary = "Completed development session with no modified files."

    # Build decisions
    decisions_list = []
    if commit_messages:
        for msg in commit_messages:
            decisions_list.append(f"Committed: {msg}")
    elif files_list:
        for f in files_list:
            decisions_list.append(f"Modified and saved {f}")
    else:
        decisions_list.append("No major decisions recorded.")

    # Build pending work
    pending_list = []
    if diagnostics:
        for diag in diagnostics:
            pending_list.append(f"Resolve diagnostic error/warning: {diag}")
    elif files_list:
        pending_list.append(f"Continue working on changes in: {files_str}")
    else:
        pending_list.append("Verify changes and plan next steps.")

    return {
        "summary": summary,
        "decisions": "\n".join(f"- {d}" for d in decisions_list),
        "pending_work": "\n".join(f"- {p}" for p in pending_list),
    }


def parse_llm_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except Exception as e:
        logger.warning(f"Failed to parse JSON from LLM response: {e}. Response was: {text}")
        raise ValueError("Invalid JSON response from LLM") from e

    decisions = data.get("decisions", [])
    if isinstance(decisions, list):
        decisions_str = "\n".join(f"- {d}" for d in decisions)
    else:
        decisions_str = str(decisions)

    pending_work = data.get("pending_work", [])
    if isinstance(pending_work, list):
        pending_work_str = "\n".join(f"- {p}" for p in pending_work)
    else:
        pending_work_str = str(pending_work)

    return {
        "summary": data.get("summary", "No summary generated."),
        "decisions": decisions_str or "No major decisions recorded.",
        "pending_work": pending_work_str or "No pending work recorded.",
    }


def call_gemini(prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        resp_data = json.loads(response.read().decode("utf-8"))

    text_content = resp_data["candidates"][0]["content"]["parts"][0]["text"]
    return parse_llm_json(text_content)


def call_openai(prompt: str) -> dict:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=10) as response:
        resp_data = json.loads(response.read().decode("utf-8"))

    text_content = resp_data["choices"][0]["message"]["content"]
    return parse_llm_json(text_content)


def generate_ai_summary(session: Session, events: list[Event]) -> dict:
    files_list = []
    if session.files:
        try:
            files_list = json.loads(session.files)
        except Exception:
            files_list = []

    # Compile chronological sequence of events
    event_details = []
    for event in events:
        time_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        detail = f"[{time_str}] {event.event_type}"
        if event.file_path:
            detail += f" - File: {event.file_path}"
        if event.metadata_:
            try:
                meta = json.loads(event.metadata_)
                useful_meta = {}
                if "message" in meta:
                    useful_meta["message"] = meta["message"]
                if "severity" in meta:
                    useful_meta["severity"] = meta["severity"]
                if "commit_hash" in meta:
                    useful_meta["commit_hash"] = meta["commit_hash"]
                if useful_meta:
                    detail += f" (Metadata: {json.dumps(useful_meta)})"
            except Exception:
                pass
        event_details.append(detail)

    formatted_events = "\n".join(event_details)

    prompt = (
        "You are an expert developer activity analyzer. Analyze the sequence of events captured during a coding session and generate a concise summary.\n\n"
        f"Session Workspace: {session.workspace}\n"
        f"Session Duration: {session.duration_seconds} seconds\n"
        f"Files Touched: {files_list}\n\n"
        "Captured Events (chronological):\n"
        f"{formatted_events}\n\n"
        "Based on this activity, please provide:\n"
        "1. A concise, one-sentence summary of what was being built or worked on.\n"
        "2. A bulleted list of key decisions made (inferred from files modified, Git commits, etc.).\n"
        "3. A bulleted list of pending/unfinished work (e.g., remaining files to edit, unresolved errors/warnings, or planned tasks).\n\n"
        "Your response must be a valid JSON object with the following format:\n"
        "{\n"
        '  "summary": "one-sentence summary of the session",\n'
        '  "decisions": [\n'
        '    "Decision 1",\n'
        '    "Decision 2"\n'
        '  ],\n'
        '  "pending_work": [\n'
        '    "Pending work item 1",\n'
        '    "Pending work item 2"\n'
        '  ]\n'
        "}\n"
        "Do not include any markdown formatting (like ```json ... ```) or extra text outside the JSON object."
    )

    if settings.GEMINI_API_KEY:
        try:
            return call_gemini(prompt)
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Trying OpenAI or falling back.")

    if settings.OPENAI_API_KEY:
        try:
            return call_openai(prompt)
        except Exception as e:
            logger.warning(f"OpenAI API call failed: {e}. Falling back to local summary.")

    return generate_local_fallback(session, events)
