"""
HTTP client for the Developer Memory OS backend API.
Uses only Python stdlib (urllib) — no extra dependencies.
"""
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Any

from devmem.config import BACKEND_URL, REQUEST_TIMEOUT


class BackendError(Exception):
    """Raised when the backend returns a non-2xx response."""

    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(f"Backend error {status}: {detail}")


def _request(path: str, method: str = "GET", params: dict | None = None, data: dict | None = None) -> Any:
    """
    Make a JSON request to the backend.
    Returns parsed JSON body.
    Raises BackendError for HTTP errors and ConnectionError for network failures.
    """
    url = f"{BACKEND_URL}{path}"
    if params:
        query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query_string:
            url = f"{url}?{query_string}"

    body_bytes = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("detail", str(body))
        except Exception:
            detail = str(exc)
        raise BackendError(exc.code, detail) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ConnectionError(
            f"Cannot connect to backend at {BACKEND_URL}. "
            "Make sure the backend server is running.\n"
            f"Hint: cd backend && python -m uvicorn app.main:app --reload"
        ) from exc


# ---------------------------------------------------------------------------
# API convenience methods
# ---------------------------------------------------------------------------

def health() -> dict:
    return _request("/health")


def get_sessions(workspace: str | None = None, limit: int = 20, offset: int = 0) -> list:
    params = {"limit": limit, "offset": offset}
    if workspace:
        params["workspace"] = workspace
    return _request("/api/sessions", params=params) or []


def get_active_session(workspace: str | None = None) -> dict | None:
    params = {}
    if workspace:
        params["workspace"] = workspace
    return _request("/api/sessions/active", params=params)


def end_active_session(workspace: str | None = None) -> dict:
    params = {}
    if workspace:
        params["workspace"] = workspace
    url = "/api/sessions/active/end"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return _request("/api/sessions/active/end", method="POST", params=params)


def search(query: str, workspace: str | None = None) -> dict:
    params: dict = {"query": query}
    if workspace:
        params["workspace"] = workspace
    return _request("/api/search", params=params)
