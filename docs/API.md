# Developer Memory OS
## REST API Contract

Version: 1.0
Status: Active

---

## 1. Health Endpoint

### `GET /health`
Returns the status of the API and database.

**Response**
* Code: `200 OK`
* Payload:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

## 2. Event Endpoints

### `POST /api/events`
Records a new development event.

**Payload**
```json
{
  "event_type": "FileSaved",
  "file_path": "backend/app/main.py",
  "workspace": "C:/Users/saaad kabir/Desktop/Full Project/Dev Memory",
  "language": "python",
  "timestamp": "2026-07-15T20:12:05Z",
  "metadata": {
    "size_bytes": 1024,
    "lines": 42
  }
}
```

**Supported Event Types**
- `FileOpened`
- `FileSaved`
- `FileClosed`
- `Diagnostic` (requires `metadata` with `severity` and `message`)
- `GitCommit` (requires `metadata` with `commit_hash` and `message`)
- `WorkspaceOpened`
- `WorkspaceClosed`

**Response**
* Code: `201 Created`
* Payload:
```json
{
  "id": 1,
  "status": "recorded",
  "session_id": 12
}
```

---

## 3. Session Endpoints

### `GET /api/sessions`
Retrieves a list of all historical development sessions.

**Query Parameters**
- `limit` (int, optional, default: 20)
- `offset` (int, optional, default: 0)
- `workspace` (string, optional)

**Response**
* Code: `200 OK`
* Payload:
```json
[
  {
    "id": 12,
    "start_time": "2026-07-15T20:00:00Z",
    "end_time": "2026-07-15T20:15:00Z",
    "duration_seconds": 900,
    "workspace": "C:/Users/saaad kabir/Desktop/Full Project/Dev Memory",
    "files": ["backend/app/main.py", "README.md"],
    "summary": "Initialized backend structure and configured git repository."
  }
]
```

### `GET /api/sessions/active`
Gets the currently active session, if any. A session is active if the last event occurred within the timeout threshold (default: 15 minutes).

**Response**
* Code: `200 OK`
* Payload (Active Session):
```json
{
  "id": 12,
  "start_time": "2026-07-15T20:00:00Z",
  "last_activity_time": "2026-07-15T20:12:05Z",
  "workspace": "C:/Users/saaad kabir/Desktop/Full Project/Dev Memory"
}
```
* Payload (No Active Session):
```json
null
```

### `POST /api/sessions/active/end`
Explicitly terminates the current active session, triggering an AI summary generation.

**Response**
* Code: `200 OK`
* Payload:
```json
{
  "status": "terminated",
  "session_id": 12,
  "summary_generated": true
}
```

---

## 4. Query & Search Endpoints

### `GET /api/search`
Searches sessions or answers natural language questions using memory context.

**Query Parameters**
- `query` (string, required) — natural language question or keyword. Examples:
  - `"What did I work on yesterday?"`
  - `"auth.py"`
  - `"resume"`
  - `"What files did I change today?"`
- `workspace` (string, optional) — filter results to a specific workspace path.

**Date keywords recognized:** `today`, `yesterday`, `this week`, `last week`

**Response**
* Code: `200 OK`
* Payload:
```json
{
  "query": "What did I work on yesterday?",
  "answer": "Yesterday, you worked on the backend foundation. You initialized FastAPI, installed SQLAlchemy, and configured SQLite.",
  "matched_sessions": [
    {
      "id": 11,
      "date": "2026-07-14",
      "summary": "FastAPI initialization and package setup."
    }
  ]
}
```

**Notes**
- If Gemini or OpenAI API keys are configured, a natural-language LLM answer is generated.
- If no API keys are set, a deterministic local answer is built from session metadata.
- If no sessions match the query, `matched_sessions` will be `[]` and `answer` will state no history was found.