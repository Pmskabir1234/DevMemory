# Developer Memory OS

An AI-powered, CLI-first developer memory system that continuously captures development activities and reconstructs your working context to eliminate context-switching.

## Key Features
- **Event Collection**: Captures file and workspace activities, diagnostics, and git commits.
- **Session Builder**: Automatically clusters raw events into continuous development sessions.
- **AI Summary**: Generates structured AI summaries detailing completed/pending work and decision logs.
- **Natural Language Query**: Retrieve context with commands like `devmem ask "What did I work on yesterday?"`.
- **Instant Resume**: Restore previous work state, open files, and pending tasks instantly.

## Project Structure
- `docs/` - System specification, progress tracking, and design decisions.
- `backend/` - FastAPI service managing database storage and AI processing.
- `cli/` - Typer-based command line interface for developer interactions.
- `extension/` - VS Code extension for automated event tracking.

## Getting Started
See the [SPECS.md](docs/SPECS.md) and [TASKS.md](docs/TASKS.md) files in the `docs` directory for system details and implementation progress.
