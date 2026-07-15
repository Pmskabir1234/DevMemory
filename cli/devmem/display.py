"""
Rich-based display helpers for consistent CLI output formatting.
"""
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


def _fmt_dt(dt_str: str | None) -> str:
    """Format an ISO datetime string to a readable form."""
    if not dt_str:
        return "—"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str


def _fmt_duration(seconds: int | None) -> str:
    if not seconds:
        return "0s"
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s or not parts:
        parts.append(f"{s}s")
    return " ".join(parts)


def print_sessions_table(sessions: list[dict]) -> None:
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Date", width=17)
    table.add_column("Duration", width=10)
    table.add_column("Workspace", overflow="fold", max_width=35)
    table.add_column("Summary", overflow="fold", max_width=50)

    for s in sessions:
        summary = (s.get("summary") or "No summary")
        if len(summary) > 80:
            summary = summary[:77] + "..."
        workspace = s.get("workspace", "—")
        table.add_row(
            str(s.get("id", "—")),
            _fmt_dt(s.get("start_time")),
            _fmt_duration(s.get("duration_seconds")),
            workspace,
            summary,
        )

    console.print(table)


def print_session_detail(session: dict) -> None:
    """Print a full session detail panel — used for `resume`."""
    sid = session.get("id", "?")
    start = _fmt_dt(session.get("start_time"))
    end = _fmt_dt(session.get("end_time"))
    duration = _fmt_duration(session.get("duration_seconds"))
    workspace = session.get("workspace", "—")
    files: list = session.get("files") or []
    summary = session.get("summary") or "No summary available."
    decisions = session.get("decisions") or "None recorded."
    pending = session.get("pending_work") or "Nothing pending."

    lines = [
        f"[bold cyan]Session #{sid}[/bold cyan]",
        f"[dim]{start}  →  {end}  ({duration})[/dim]",
        f"[dim]Workspace:[/dim] {workspace}",
        "",
        "[bold]Summary[/bold]",
        f"  {summary}",
        "",
    ]

    if files:
        lines.append("[bold]Files Touched[/bold]")
        for f in files:
            lines.append(f"  [green]•[/green] {f}")
        lines.append("")

    lines.append("[bold]Decisions Made[/bold]")
    for line in decisions.splitlines():
        lines.append(f"  {line}")
    lines.append("")

    lines.append("[bold]Pending Work[/bold]")
    for line in pending.splitlines():
        lines.append(f"  [yellow]{line}[/yellow]")

    content = "\n".join(lines)
    console.print(Panel(content, title="[bold]Resume — Last Session[/bold]", border_style="cyan"))


def print_search_result(result: dict) -> None:
    """Print the answer from a search/ask query."""
    query = result.get("query", "")
    answer = result.get("answer", "No answer generated.")
    matched = result.get("matched_sessions", [])

    console.print()
    console.print(Panel(answer, title=f"[bold cyan]Answer to:[/bold cyan] {query}", border_style="cyan"))

    if matched:
        console.print(f"\n[dim]Based on {len(matched)} matched session(s):[/dim]")
        for s in matched:
            console.print(f"  [dim]• Session {s['id']} ({s['date']}) — {s['summary'][:80]}[/dim]")
    console.print()


def print_active_session(session: dict | None) -> None:
    if session is None:
        console.print("[yellow]No active session right now.[/yellow]")
        return

    start = _fmt_dt(session.get("start_time"))
    last = _fmt_dt(session.get("last_activity_time"))
    workspace = session.get("workspace", "—")

    console.print(
        Panel(
            f"[bold]Session #{session['id']}[/bold]\n"
            f"Started:       {start}\n"
            f"Last activity: {last}\n"
            f"Workspace:     {workspace}",
            title="[bold cyan]Active Session[/bold cyan]",
            border_style="green",
        )
    )


def error(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")


def success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def info(msg: str) -> None:
    console.print(f"[cyan]ℹ[/cyan] {msg}")
