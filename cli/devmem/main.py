"""
devmem — Developer Memory OS CLI

Commands:
  history   Show past development sessions
  sessions  Alias for history (with active session indicator)
  resume    Restore context from the last completed session
  ask       Ask a natural language question about your work history
  search    Search sessions by keyword or file name
  health    Check backend health status
  version   Show CLI version
"""
import sys
from typing import Optional

import typer
from rich.console import Console

from devmem import config
from devmem import client as api
from devmem import display
from devmem.client import BackendError

app = typer.Typer(
    name="devmem",
    help="Developer Memory OS — remember what you worked on.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


# Shared option defaults

_WORKSPACE_OPT = typer.Option(
    None, "--workspace", "-w", help="Filter by workspace path."
)
_LIMIT_OPT = typer.Option(
    config.DEFAULT_LIMIT, "--limit", "-n", help="Maximum number of results.", min=1, max=100
)




# helpers

def _handle_error(exc: Exception) -> None:
    """Print a friendly error and exit."""
    if isinstance(exc, BackendError):
        display.error(f"{exc.detail}")
    elif isinstance(exc, ConnectionError):
        display.error(str(exc))
    else:
        display.error(str(exc))
    raise typer.Exit(code=1)



# Commands

@app.command()
def history(
    workspace: Optional[str] = _WORKSPACE_OPT,
    limit: int = _LIMIT_OPT,
    offset: int = typer.Option(0, "--offset", help="Skip this many results."),
) -> None:
    """Show past development sessions."""
    try:
        sessions = api.get_sessions(workspace=workspace, limit=limit, offset=offset)
    except Exception as exc:
        _handle_error(exc)
        return

    if not sessions:
        display.info("No completed sessions found.")
        return

    display.print_sessions_table(sessions)
    console.print(f"[dim]Showing {len(sessions)} session(s). Use --limit / --offset to paginate.[/dim]")


@app.command()
def sessions(
    workspace: Optional[str] = _WORKSPACE_OPT,
    limit: int = _LIMIT_OPT,
) -> None:
    """List sessions and show whether a session is currently active."""
    try:
        all_sessions = api.get_sessions(workspace=workspace, limit=limit)
        active = api.get_active_session(workspace=workspace)
    except Exception as exc:
        _handle_error(exc)
        return

    # Show active session first if present
    if active:
        display.print_active_session(active)
        console.print()

    if all_sessions:
        display.print_sessions_table(all_sessions)
    else:
        display.info("No completed sessions yet.")


@app.command()
def resume(
    workspace: Optional[str] = _WORKSPACE_OPT,
) -> None:
    """Restore context from the last completed session."""
    try:
        all_sessions = api.get_sessions(workspace=workspace, limit=1)
    except Exception as exc:
        _handle_error(exc)
        return

    if not all_sessions:
        display.info("No completed sessions found. Start working and then end a session first.")
        return

    display.print_session_detail(all_sessions[0])


@app.command()
def ask(
    question: str = typer.Argument(..., help='Natural language question, e.g. "What did I work on yesterday?"'),
    workspace: Optional[str] = _WORKSPACE_OPT,
) -> None:
    """Ask a natural language question about your development history."""
    try:
        result = api.search(query=question, workspace=workspace)
    except Exception as exc:
        _handle_error(exc)
        return

    display.print_search_result(result)


@app.command()
def search(
    keyword: str = typer.Argument(..., help="Keyword, file name, or topic to search for."),
    workspace: Optional[str] = _WORKSPACE_OPT,
    limit: int = _LIMIT_OPT,
) -> None:
    """Search sessions by keyword, file name, or topic."""
    try:
        result = api.search(query=keyword, workspace=workspace)
    except Exception as exc:
        _handle_error(exc)
        return

    display.print_search_result(result)


@app.command()
def health() -> None:
    """Check the backend health status."""
    try:
        data = api.health()
    except ConnectionError as exc:
        display.error(str(exc))
        raise typer.Exit(code=1)
    except BackendError as exc:
        display.error(f"Backend returned {exc.status}: {exc.detail}")
        raise typer.Exit(code=1)
    except Exception as exc:
        display.error(str(exc))
        raise typer.Exit(code=1)

    status_val = data.get("status", "unknown")
    db_val = data.get("database", "unknown")

    if status_val == "healthy" and db_val == "connected":
        display.success(f"Backend is [bold green]healthy[/bold green]. Database: [bold green]{db_val}[/bold green].")
    else:
        display.error(f"Backend status: {status_val}, Database: {db_val}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show the devmem CLI version."""
    console.print(f"devmem CLI [bold cyan]v{config.VERSION}[/bold cyan]")
    console.print(f"Backend: [dim]{config.BACKEND_URL}[/dim]")



# Entry point
def main() -> None:
    app()


if __name__ == "__main__":
    main()
