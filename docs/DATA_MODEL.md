# Developer Memory OS
## Database Schema & Data Models

Version: 1.0
Status: Active

---

## 1. Database Choice
The system uses **SQLite** for local-first storage. It requires zero setup and provides sufficient transaction support and speed for single-developer memory logs.

---

## 2. Table Schemas

### `events` Table
Stores raw activity events captured from VS Code or git commands.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ID for the event |
| `event_type` | VARCHAR(50) | NOT NULL | Type of event (e.g. `FileSaved`, `Diagnostic`, `GitCommit`) |
| `file_path` | TEXT | NULL | Path to the file involved, relative to workspace or absolute |
| `workspace` | TEXT | NOT NULL | Workspace absolute path |
| `language` | VARCHAR(50) | NULL | Programming language identifier (e.g. `python`, `typescript`) |
| `timestamp` | DATETIME | NOT NULL | Timestamp when event occurred (UTC) |
| `metadata` | JSON / TEXT | NULL | Additional metadata (diagnostics, commit messages, size, lines) |
| `session_id` | INTEGER | FOREIGN KEY | Associates the event with a parent session |

---

### `sessions` Table
Stores development sessions clustered by period of active coding.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique ID for the session |
| `summary` | TEXT | NULL | AI-generated summary of work done |
| `start_time` | DATETIME | NOT NULL | Session start timestamp (UTC) |
| `end_time` | DATETIME | NOT NULL | Session end timestamp (UTC) |
| `duration_seconds` | INTEGER | NOT NULL | Duration of the session in seconds |
| `workspace` | TEXT | NOT NULL | Workspace absolute path |
| `files` | TEXT | NULL | JSON string array of files touched during the session |
| `pending_work` | TEXT | NULL | AI-inferred lists of pending TODOs / next steps |
| `decisions` | TEXT | NULL | AI-inferred decision log |

---

## 3. Relationships
- **One-to-Many**: A `Session` has many `Events`.
- When an event is created, the system checks for an active session in the same `workspace` where `timestamp - last_event_timestamp <= 15 minutes`.
  - If one exists, the event is associated with it.
  - If not, a new session is created.