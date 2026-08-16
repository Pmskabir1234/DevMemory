# Developer Memory OS

> **A local-first, CLI-driven developer memory system that captures coding activities in real-time, clusters events into structured work sessions, generates AI-powered summaries, and restores your working context instantly.**

[![Tests](https://img.shields.io/badge/tests-103%20passed-brightgreen)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-teal)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/database-SQLite-lightgrey)](https://www.sqlite.org/)
[![VS Code](https://img.shields.io/badge/VS%20Code-Extension-007ACC)](https://code.visualstudio.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of Contents:

- [Vision & Problem Statement](#vision--problem-statement)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Project Layout](#project-layout)
- [Getting Started](#getting-started)
  - [1. Backend Service Setup](#1-backend-service-setup)
  - [2. CLI Installation](#2-cli-installation)
  - [3. VS Code Extension Setup](#3-vs-code-extension-setup)
- [CLI Reference](#cli-reference)
- [Configuration](#configuration)
- [REST API Reference](#rest-api-reference)
- [Running Tests](#running-tests)
- [Documentation Index](#documentation-index)
- [License](#license)

---

## Vision & Problem Statement:

Developers constantly lose context because software development is fragmented across dozens of tools: Git remembers commits, VS Code remembers open tabs, the terminal remembers command history, and AI chatbots remember conversations—but **no single tool remembers your entire workflow**.

After interruptions or returning the next day, engineers waste precious time figuring out:
- Which files were being modified?
- What was the feature or bug being worked on?
- What architectural decisions were made?
- What tasks remain unfinished?

**Developer Memory OS** solves this problem by passively recording development signals from your editor, automatically grouping them into sessions (15-minute inactivity threshold), generating AI summaries (via Google Gemma / LangChain), and letting you query and resume previous work instantly via the `devmem` CLI.

---

## Key Features

- **Automated Event Capture**: Listens to file opens, saves, closes, workspace changes, and diagnostics from VS Code without manual logging.
- **Intelligent Session Builder**: Clusters raw events into cohesive work sessions using temporal boundaries.
- **AI Session Summaries**: Generates structured summaries, decision logs, and pending TODOs using Google Gemma (with 100% offline local fallback).
- **Natural Language Search**: Ask questions like `"What did I work on yesterday?"` or `"Which file did I edit last?"`.
- **Instant Resume**: Run `devmem resume` to restore your exact context, touched files, and pending items.
- **Privacy & Local-First**: Stores metadata and sessions in local SQLite. Your full source code is never uploaded.
- **Resilient Delivery**: Automatic 3-retry HTTP client with backoff ensures events are never dropped during backend restarts.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   VS Code Extension                      │
│   (Captures: FileSaved, FileOpened, Diagnostic, Git)     │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTP POST /api/events
                             │ (3x retry & backoff)
                             ▼
┌──────────────────────────────────────────────────────────┐
│               FastAPI Backend (Port 8000)                │
│                                                          │
│  ┌────────────────────┐       ┌───────────────────────┐  │
│  │   Event Ingestion  │       │    Session Builder    │  │
│  │    & Validation    │──────▶│ (15-min timeout rule) │  │
│  └────────────────────┘       └───────────┬───────────┘  │
│                                           │              │
│  ┌────────────────────┐       ┌───────────▼───────────┐  │
│  │ Natural Language   │       │   Summary Generator   │  │
│  │   Search Service   │       │  (LangChain + Gemma)  │  │
│  └──────────┬─────────┘       └───────────┬───────────┘  │
│             │                             │              │
│             └──────────────┬──────────────┘              │
│                            ▼                             │
│                  ┌───────────────────┐                   │
│                  │  SQLite Database  │                   │
│                  │ (events, sessions)│                   │
│                  └───────────────────┘                   │
└────────────────────────────▲─────────────────────────────┘
                             │
                             │ REST API (/api/search, /api/sessions)
┌────────────────────────────┴─────────────────────────────┐
│                       devmem CLI                         │
│  Commands: history, sessions, resume, ask, search,       │
│            health, version                               │
└──────────────────────────────────────────────────────────┘
```

For detailed architecture, sequence diagrams, and design records, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DECISIONS.md](docs/DECISIONS.md).

---

## Project Layout:

```
Dev Memory/
├── backend/                  # FastAPI backend service
│   ├── alembic/              # Database schema migrations
│   ├── app/
│   │   ├── api/              # REST routes (/events, /sessions, /search, /health)
│   │   ├── core/             # Configuration and logging
│   │   ├── db/               # SQLAlchemy SQLite engine and Base models
│   │   ├── models/           # Event and Session ORM models
│   │   ├── schemas/          # Pydantic v2 validation schemas
│   │   └── services/         # Event, Session, Summary, and Search business logic
│   ├── tests/                # Pytest unit & API test suites + integration runner
│   └── requirements.txt      # Backend Python dependencies
├── cli/                      # Typer CLI application (devmem)
│   ├── devmem/               # CLI source code (commands, formatting, HTTP client)
│   ├── tests/                # CLI unit tests
│   ├── pyproject.toml        # Packaging configuration (pip install -e .)
│   └── requirements.txt      # CLI dependencies
├── extension/                # VS Code event tracking extension
│   ├── src/                  # TypeScript source (client, filter, eventBuilder, extension)
│   ├── test/                 # Extension test suite (Mocha)
│   └── package.json          # VS Code extension manifest
├── docs/                     # System specifications & tracking
│   ├── SPECS.md              # Functional specifications
│   ├── ARCHITECTURE.md       # Architecture & component diagrams
│   ├── DATA_MODEL.md         # Database schema & entity models
│   ├── API.md                # REST API contract
│   ├── DECISIONS.md          # Architecture Decision Records (ADRs)
│   ├── PROMPTS.md            # LLM prompt templates & parser definitions
│   ├── TASKS.md              # Master development task list
│   └── PROGRESS.md           # Development progress & session logs
├── pytest.ini                # Pytest configuration
└── README.md                 # System overview and guide
```

---

## Getting Started

### Prerequisites

- **Python**: 3.10 or higher
- **Node.js**: 18.x or higher (for the VS Code extension)
- **VS Code**: 1.85.0 or higher

---

### 1. Backend Service Setup

1. **Activate Virtual Environment**:
   ```bash
   # Windows
   .\venv\Scripts\activate

   # Linux / macOS
   source venv/bin/activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Configure Environment Variables** (Optional):
   Create `backend/.env` (or set environment variables):
   ```ini
   DATABASE_URL=sqlite:///./devmem.db
   PORT=8000
   HF_API_KEY=your_huggingface_api_key_here
   HF_MODEL_ID=google/gemma-2-2b-it
   LOG_LEVEL=INFO
   ```
   > **Note**: If `HF_API_KEY` is omitted, Developer Memory OS will seamlessly use its built-in offline deterministic fallback for all summaries and queries.

4. **Run Database Migrations**:
   ```bash
   cd backend
   alembic upgrade head
   cd ..
   ```

5. **Start the Backend Server**:
   ```bash
   uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
   Verify the server is running by opening `http://127.0.0.1:8000/docs` (Swagger UI).

---

### 2. CLI Installation

You can install the CLI in editable mode so the `devmem` command is globally available inside your environment:

```bash
cd cli
pip install -e .
cd ..
```

Verify the installation:
```bash
devmem --help
```

---

### 3. VS Code Extension Setup

1. **Install Extension Dependencies & Compile**:
   ```bash
   cd extension
   npm install
   npm run compile
   cd ..
   ```

2. **Run in Development Mode**:
   - Open the `extension` folder in VS Code.
   - Press <kbd>F5</kbd> to launch the **Extension Development Host**.
   - The status bar will display **`$(database) devmem`**, indicating background event capture is active.

3. **Package as VSIX** (Optional for distribution):
   ```bash
   cd extension
   npx @vscode/vsce package
   ```
   Install the generated `.vsix` in VS Code via **Extensions → ... → Install from VSIX**.

---

## CLI Reference

The `devmem` command line tool provides full visibility into your development history:

```text
Usage: devmem [OPTIONS] COMMAND [ARGS]...

  Developer Memory OS — CLI interface.
```

### Commands

| Command | Description | Example |
|---|---|---|
| `devmem resume` | Restore context from your last completed session | `devmem resume` |
| `devmem history` | Display list of past completed sessions with pagination | `devmem history --limit 5` |
| `devmem sessions`| View active session status and recent sessions | `devmem sessions` |
| `devmem ask` | Ask natural-language questions about your work history | `devmem ask "What did I work on yesterday?"` |
| `devmem search` | Keyword and date-filtered search | `devmem search "auth.py"` |
| `devmem health` | Check backend server status | `devmem health` |
| `devmem version`| Display version and backend configuration | `devmem version` |

### Practical Examples

#### Restoring Context with `devmem resume`
```bash
$ devmem resume

  Session #12 (2026-08-16 15:30)
  Workspace: C:/projects/my-app
  Duration : 45 minutes

  Summary  : Implemented user authentication with JWT and refresh tokens.
  Files    : backend/auth.py, backend/models/user.py, backend/api/auth.py

  Decisions:
  - Added bcrypt password hashing
  - Created refresh token rotation middleware

  Pending Work:
  - Add unit tests for token expiration
  - Implement logout token invalidation blacklist
```

#### Natural Language Q&A with `devmem ask`
```bash
$ devmem ask "Which file did I edit last?"
You last edited 'backend/app/services/summary.py' during your session on 2026-08-16.

$ devmem ask "What work is pending?"
Pending tasks from recent sessions:
- Add unit tests for token expiration
- Resolve diagnostic warning in backend/app/schemas/session.py
```

#### Searching Sessions with `devmem search`
```bash
$ devmem search auth.py
Found 2 matching sessions:
• Session #12 (2026-08-16 15:30) — Implemented user authentication with JWT and refresh tokens.
• Session #9  (2026-08-14 10:15) — Initial user schema and password hashing setup.
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./devmem.db` | SQLAlchemy SQLite database connection string |
| `PORT` | `8000` | Backend listening port |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `HF_API_KEY` | *(None / Local)* | Hugging Face API token for Google Gemma inference |
| `HF_MODEL_ID` | `google/gemma-2-2b-it` | Hugging Face model repository ID |
| `DEVMEM_BACKEND_URL` | `http://127.0.0.1:8000` | Backend API URL used by CLI and VS Code extension |

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server and database health check |
| `POST` | `/api/events` | Ingests a new development event (`FileSaved`, `Diagnostic`, etc.) |
| `GET` | `/api/sessions` | Lists paginated historical sessions (`limit`, `offset`, `workspace`) |
| `GET` | `/api/sessions/active` | Gets currently active session for a workspace |
| `POST` | `/api/sessions/active/end` | Explicitly ends the active session and triggers AI summary |
| `GET` | `/api/search` | Natural language Q&A and keyword search (`query`, `workspace`) |

For full request/response schemas and examples, see [docs/API.md](docs/API.md).

---

## Running Tests

Developer Memory OS features comprehensive multi-tier test suites (103 total tests):

### 1. Run All Backend & CLI Unit Tests (Pytest)
```bash
python -m pytest
```
*Executes 77 unit tests covering API endpoints, services, schemas, and CLI commands.*

### 2. Run VS Code Extension Tests (Mocha)
```bash
cd extension
npm test
cd ..
```
*Executes 14 unit tests covering event filtering, relative path calculations, and retry logic.*

### 3. Run End-to-End Integration Suite
```bash
python backend/tests/run_tests.py
```
*Starts an isolated test server against a temporary database and executes 12 end-to-end integration scenarios.*

---

## Documentation Index

| File | Content |
|---|---|
| [docs/SPECS.md](docs/SPECS.md) | Product vision, functional requirements, and MVP scope |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Component architecture, data flows, and subsystem specifications |
| [docs/API.md](docs/API.md) | Full REST API contract and endpoint documentation |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | SQLite schema, table structures, and entity relationships |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Architecture Decision Records (ADRs) |
| [docs/PROMPTS.md](docs/PROMPTS.md) | LangChain LCEL prompts and Pydantic output parser schemas |
| [docs/TASKS.md](docs/TASKS.md) | Master development roadmap and phase checklists |
| [docs/PROGRESS.md](docs/PROGRESS.md) | Detailed development logs and session history |

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
