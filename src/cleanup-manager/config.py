"""
Cleanup Manager - Configuration

Type-safe configuration loaded from environment variables (and optionally
a .env file). Reuses the same variable names as the runner agents
(GITHUB_ACCESS_TOKEN, APP_ID, ORG_NAME, ...) so the cleanup-manager
can share a single .env without duplication.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cleanup manager settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === GitHub authentication (PAT preferred, App fallback) ===
    github_access_token: str = Field(
        default="",
        description="Personal access token with admin:org or repo scope",
    )
    app_id: str = Field(
        default="",
        description="GitHub App ID for installation-token auth",
    )
    app_private_key_file: str = Field(
        default="/opt/github-app.pem",
        description="Path to the GitHub App PEM private key (mounted via app-auth override)",
    )

    # === Scope (what runners to clean) ===
    org_name: str = Field(
        default="",
        description="Organization slug for org-level runners",
    )
    repo_url: str = Field(
        default="",
        description="Repository URL for repo-level runners (alternative to ORG_NAME)",
    )
    runner_scope: Literal["org", "repo"] = Field(
        default="org",
        description="Whether to clean organization or repository runners",
    )

    # === Cleanup behavior ===
    cleanup_min_age_days: int = Field(
        default=1,
        ge=0,
        description="Skip runners that registered less than N days ago",
    )
    cleanup_reserve_pct: float = Field(
        default=0.10,
        ge=0.0,
        le=0.5,
        description="Fraction of rate-limit bucket to reserve for other consumers",
    )
    cleanup_floor_delay: float = Field(
        default=0.5,
        ge=0.0,
        description="Minimum seconds between API requests (secondary-limit guard)",
    )
    cleanup_run_on_startup: bool = Field(
        default=False,
        description="Run a cleanup pass immediately on container start",
    )

    # === Schedule ===
    cleanup_schedule_enabled: bool = Field(
        default=True,
        description="Enable the scheduled cleanup runs",
    )
    cleanup_schedule_mode: Literal["cron", "interval"] = Field(
        default="cron",
        description="Schedule mode: 'cron' (fixed time) or 'interval' (every N hours)",
    )
    cleanup_schedule_hour: int = Field(
        default=4,
        ge=0,
        le=23,
        description="Hour to run cleanup (cron mode)",
    )
    cleanup_schedule_minute: int = Field(
        default=0,
        ge=0,
        le=59,
        description="Minute to run cleanup (cron mode)",
    )
    cleanup_schedule_day_of_week: str = Field(
        default="6",
        description="Day(s) of week for cron mode. 0=Mon, 6=Sun. Use '*' for daily, '0,3' for Mon&Thu",
    )
    cleanup_schedule_interval_hours: int = Field(
        default=168,
        ge=1,
        le=720,
        description="Hours between cleanup runs (interval mode). Default 168 = weekly",
    )

    # === Misc ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging verbosity",
    )
    time_zone: str = Field(
        default="Etc/UTC",
        alias="TZ",
        description="Timezone for cron schedule and timestamps",
    )

    # ---- Computed scope helpers ----

    @property
    def api_scope(self) -> str:
        """Return the GitHub API URL fragment for the configured scope."""
        if self.runner_scope == "org" and self.org_name:
            return f"orgs/{self.org_name}"
        if self.runner_scope == "repo" and self.repo_url:
            from urllib.parse import urlparse
            path = urlparse(self.repo_url).path.strip("/")
            return f"repos/{path}"
        # Fallback: prefer org if both are set
        if self.org_name:
            return f"orgs/{self.org_name}"
        if self.repo_url:
            from urllib.parse import urlparse
            path = urlparse(self.repo_url).path.strip("/")
            return f"repos/{path}"
        raise ValueError("Neither ORG_NAME nor REPO_URL is configured")

    @property
    def app_install_scope(self) -> str:
        """Where to look up the App installation for token exchange."""
        if self.org_name:
            return f"orgs/{self.org_name}"
        if self.repo_url:
            from urllib.parse import urlparse
            owner = urlparse(self.repo_url).path.strip("/").split("/")[0]
            return f"orgs/{owner}"
        raise ValueError("App auth needs ORG_NAME or REPO_URL to locate the installation")

    @property
    def has_pat_auth(self) -> bool:
        """True if a usable PAT is configured (not the .env.example placeholder)."""
        token = (self.github_access_token or "").strip()
        return bool(token) and not token.startswith("ghp_xxxxxxxx")

    @property
    def has_app_auth(self) -> bool:
        """True if GitHub App credentials look usable."""
        return bool((self.app_id or "").strip())

    @field_validator("cleanup_schedule_day_of_week")
    @classmethod
    def _validate_dow(cls, v: str) -> str:
        v = v.strip()
        if v == "*":
            return v
        for part in v.split(","):
            part = part.strip()
            if not part.isdigit() or not (0 <= int(part) <= 6):
                raise ValueError(
                    f"Invalid day_of_week '{part}'. Use 0-6 (0=Mon, 6=Sun) or '*'"
                )
        return v
