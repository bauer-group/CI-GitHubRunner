#!/usr/bin/env python3
"""
GitHub Runner Cleanup Manager - Entry Point

Modes:
    python main.py            Service mode (scheduled, blocks until SIGTERM)
    python main.py --now      Run one cleanup pass immediately, then exit

Reads configuration from environment variables (or .env if present in
the working directory). The same variable names used by the runner
agents (GITHUB_ACCESS_TOKEN, APP_ID, ORG_NAME, ...) are reused here.
"""

import sys

from config import Settings
from console import cleanup_logger, console, print_banner, setup_logging
from github_api import run_cleanup
from scheduler import setup_scheduler


def main() -> int:
    try:
        settings = Settings()
    except Exception as e:
        # Pydantic validation errors are user-actionable; show them clearly.
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    setup_logging(settings.log_level)
    print_banner()

    immediate_mode = "--now" in sys.argv

    if immediate_mode:
        cleanup_logger.info("Running cleanup pass immediately (--now)...")
        success = run_cleanup(settings)
        return 0 if success else 1

    # Service mode (default): scheduler blocks the process
    cleanup_logger.info("Starting GitHub Runner Cleanup Manager (service mode)")
    scheduler = setup_scheduler(settings, lambda: run_cleanup(settings))
    try:
        scheduler.start()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
