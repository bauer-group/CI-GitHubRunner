"""
Cleanup Manager - Console UI

Rich-based logger and panel helpers, mirroring the BackupLogger pattern
from CS-GitHubBackup so the visual style stays consistent across the
BAUER GROUP container fleet.
"""

import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

console = Console()


class CleanupLogger:
    """Two-mode logger: user-facing (no timestamps, colored) and debug (timestamped)."""

    def __init__(self, name: str = "cleanup"):
        self._logger = logging.getLogger(name)

    def info(self, message: str, style: str = "dim") -> None:
        console.print(f"[{style}]{message}[/]")

    def success(self, message: str) -> None:
        console.print(f"[green]+ {message}[/]")

    def warning(self, message: str) -> None:
        console.print(f"[yellow]! {message}[/]")

    def error(self, message: str) -> None:
        console.print(f"[red]x {message}[/]")

    def status(self, message: str) -> None:
        console.print(f"[dim]{message}[/]")

    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def system(self, message: str) -> None:
        self._logger.info(message)


cleanup_logger = CleanupLogger()


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging with a Rich handler."""
    root = logging.getLogger()
    root.setLevel(level)
    for h in root.handlers[:]:
        root.removeHandler(h)
    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        show_time=level == "DEBUG",
        show_level=level == "DEBUG",
        show_path=level == "DEBUG",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(handler)


def print_banner() -> None:
    console.print(Panel.fit(
        "[bold blue]GitHub Runner Cleanup Manager[/]\n"
        "[dim]Scheduled removal of leaked offline runner registrations[/]",
        border_style="blue",
    ))
    console.print()


def print_scheduler_info(description: str, next_run: str | None = None) -> None:
    console.print(f"[dim]Schedule:[/] [cyan]{description}[/]")
    if next_run:
        console.print(f"[dim]Next run:[/] [cyan]{next_run}[/]")
    console.print()


def fmt_duration(sec: float) -> str:
    sec = max(int(sec), 0)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m{sec % 60:02d}s"
    return f"{sec // 3600}h{(sec % 3600) // 60:02d}m"
