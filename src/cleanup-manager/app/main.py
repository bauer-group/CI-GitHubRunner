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

import os
import sys
from pathlib import Path

from config import Settings
from console import cleanup_logger, console, print_banner, setup_logging
from github_api import run_cleanup
from scheduler import setup_scheduler


# Constants for the unprivileged user baked into the Dockerfile.
# When running outside the container these are no-ops because
# os.geteuid() != 0 short-circuits the drop.
DROP_UID = int(os.environ.get("DROP_UID", "1000"))
DROP_GID = int(os.environ.get("DROP_GID", "1000"))


def _drop_privileges_after_reading_secrets() -> None:
    """Read mode-0600 host secrets as root, then drop to unprivileged uid.

    Pattern:
      1. While still uid 0, read the GitHub App PEM (typically 0600
         root:root on the host) into an env var so the rest of the
         process can use it without filesystem access.
      2. Drop GID then UID to the cleanup user. After this point the
         process cannot regain root, even if a subsequent code path
         is compromised.
      3. Continue with normal startup as the unprivileged user.

    No-op when already running unprivileged (e.g. local dev outside
    the container).
    """
    if os.geteuid() != 0:
        return

    pem_path = Path(os.environ.get("APP_PRIVATE_KEY_FILE", "/opt/github-app.pem"))
    if pem_path.is_file():
        try:
            os.environ["APP_PRIVATE_KEY"] = pem_path.read_text(encoding="ascii")
        except (OSError, UnicodeDecodeError) as e:
            # auth.py will surface a clearer error later if the key is needed
            print(f"warning: could not preload PEM into env: {e}", file=sys.stderr)

    # GID must be dropped before UID; once we're non-root setgid is denied.
    try:
        os.setgroups([])  # clear any supplementary groups
        os.setgid(DROP_GID)
        os.setuid(DROP_UID)
    except OSError as e:
        print(
            f"warning: failed to drop privileges to {DROP_UID}:{DROP_GID}: {e}\n"
            "Continuing as root - investigate Dockerfile/entrypoint.",
            file=sys.stderr,
        )


def main() -> int:
    _drop_privileges_after_reading_secrets()

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
