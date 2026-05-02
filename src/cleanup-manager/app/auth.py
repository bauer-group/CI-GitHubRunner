"""
Cleanup Manager - Authentication

PAT (preferred) or GitHub App auth. App auth uses PyJWT for RS256
signing and exchanges the JWT for a short-lived installation token
(typically 1 hour validity).

The installation token from a GitHub App carries the App's permissions
- if the App has 'Organization > Self-hosted runners (Read & Write)',
the token is sufficient for runner-list and runner-delete.

PEM key resolution order (so the unprivileged container user never
needs filesystem access to the host-mounted 0600 PEM):

    1. APP_PRIVATE_KEY env var (preferred). main.py reads the PEM
       while still root and exports it here, then drops privileges.
       After the drop, only this in-memory copy is reachable.
    2. APP_PRIVATE_KEY_FILE path (fallback). For local dev where the
       process runs as the file's owner directly.
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import jwt

from config import Settings
from console import cleanup_logger


def _resolve_pem(private_key_path: Path) -> bytes:
    """Return PEM bytes from env (preferred) or file (fallback)."""
    env_pem = os.environ.get("APP_PRIVATE_KEY", "").strip()
    if env_pem:
        return env_pem.encode("ascii")
    if private_key_path.is_file():
        return private_key_path.read_bytes()
    raise FileNotFoundError(
        f"GitHub App private key not available: APP_PRIVATE_KEY env var is "
        f"empty and the fallback path {private_key_path} is not readable. "
        "Check that the PEM is mounted into the container and that the "
        "entrypoint ran as root long enough to preload it."
    )


def make_jwt(app_id: str, private_key_path: Path) -> str:
    """Sign a GitHub App JWT (RS256) using the App's private key."""
    pem = _resolve_pem(private_key_path)
    now = int(time.time())
    payload = {
        "iat": now - 60,    # 60s clock skew tolerance
        "exp": now + 540,   # GitHub max is 600s, leave 60s margin
        "iss": str(app_id),
    }
    return jwt.encode(payload, pem, algorithm="RS256")


def get_installation_token(app_jwt: str, install_scope: str) -> str:
    """Exchange a GitHub App JWT for an installation access token."""
    base = "https://api.github.com"

    # 1. Look up the installation for this org/repo
    inst = _api_get(f"{base}/{install_scope}/installation", app_jwt)

    # 2. Create a fresh installation token
    tok = _api_post(f"{base}/app/installations/{inst['id']}/access_tokens", app_jwt)
    return tok["token"]


def resolve_token(settings: Settings) -> tuple[str, str]:
    """Return (access_token, label) for use with the GitHub API.

    Prefers PAT if explicitly set; falls back to App installation token.
    """
    if settings.has_pat_auth:
        return settings.github_access_token.strip(), "PAT (GITHUB_ACCESS_TOKEN)"

    if settings.has_app_auth:
        pem_path = Path(settings.app_private_key_file)
        cleanup_logger.info(
            f"Using GitHub App auth (App ID {settings.app_id}, "
            f"key at {pem_path})"
        )
        app_jwt = make_jwt(settings.app_id, pem_path)
        token = get_installation_token(app_jwt, settings.app_install_scope)
        return token, f"GitHub App {settings.app_id} (installation token)"

    raise ValueError(
        "No usable auth in environment. Set GITHUB_ACCESS_TOKEN (PAT) or "
        "APP_ID + a PEM file at APP_PRIVATE_KEY_FILE."
    )


# --- internal HTTP helpers used only during auth bootstrap ---

def _api_get(url: str, token: str) -> dict:
    return _api_request(url, token, method="GET")


def _api_post(url: str, token: str) -> dict:
    return _api_request(url, token, method="POST", body=b"")


def _api_request(url: str, token: str, method: str, body: bytes | None = None) -> dict:
    req = urllib.request.Request(url, method=method, data=body)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "bauer-group-runner-cleanup")
    if body is not None:
        req.add_header("Content-Length", str(len(body)))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(
            f"GitHub API {method} {url} failed: HTTP {e.code} - {body_text[:200]}"
        ) from e
