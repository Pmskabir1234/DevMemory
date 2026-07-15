# devmem CLI

Typer-based command line interface for Developer Memory OS.

---

## Installation

### Option 1 — Run directly from the repo (recommended during development)

```bash
# From the project root, activate the venv
cd "Full Project/Dev Memory"
venv\Scripts\activate

# Then run from the cli/ directory
cd cli
python -m devmem.main --help
```

### Option 2 — Install as a package (creates the `devmem` command)

```bash
cd cli
pip install -e .
devmem --help
```

---

## Configuration

| Variable              | Default                  | Description                        |
|-----------------------|--------------------------|------------------------------------|
| `DEVMEM_BACKEND_URL`  | `http://127.0.0.1:8000`  | URL of the running backend server  |

Set via environment variable or a `.env` file in the cli directory.

---

## Commands

### `devmem history`
Show past completed development sessions.

```bash
devmem history
devmem history --limit 5
devmem history --workspace "C:/projects/myapp"
devmem history --limit 10 --offset 20
```

---

### `devmem sessions`
List sessions and show the currently active session (if any).

```bash
devmem sessions
devmem sessions --workspace "C:/projects/myapp"
```

---

### `devmem resume`
Restore your last completed session — shows summary, files touched, decisions, and pending work.

```bash
devmem resume
devmem resume --workspace "C:/projects/myapp"
```

---

### `devmem ask`
Ask a natural language question about your development history. Uses an LLM if configured, otherwise answers from stored metadata.

```bash
devmem ask "What did I work on yesterday?"
devmem ask "Which file did I edit last?"
devmem ask "Show me my authentication work"
devmem ask "What is pending from my last session?"
```

---

### `devmem search`
Search sessions by keyword, file name, or topic.

```bash
devmem search auth.py
devmem search "database migration"
devmem search main.py --workspace "C:/projects/myapp"
```

---

### `devmem health`
Check whether the backend server is running and healthy.

```bash
devmem health
```

---

### `devmem version`
Show CLI version and backend URL.

```bash
devmem version
```

---

## Prerequisites

- Python 3.10+
- Backend server running (`cd backend && uvicorn app.main:app --reload`)
- Dependencies: `typer`, `rich` (installed via `pip install -e .` or `pip install -r requirements.txt`)
