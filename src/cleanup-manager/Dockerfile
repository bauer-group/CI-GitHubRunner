# =============================================================================
# GitHub Runner - Cleanup Manager
# =============================================================================
# Long-running helper that periodically removes leaked offline-runner
# registrations from the GitHub organization. Runs as a sidecar in the
# runner stack, reusing the same .env credentials as the agents.
#
# Behavior:
#   - On schedule (default: weekly Sunday 04:00 local TZ): list runners,
#     filter offline + min-age, delete via GitHub API with adaptive pacing.
#   - On startup (optional via CLEANUP_RUN_ON_STARTUP=true): run once
#     immediately, then continue with the schedule.
#   - On SIGTERM: stop the scheduler gracefully and let the current
#     cleanup pass finish (capped by stop_grace_period).
#
# Authentication:
#   - PAT via GITHUB_ACCESS_TOKEN, OR
#   - GitHub App via APP_ID + a PEM mounted at /opt/github-app.pem
#     (handled by docker-compose.app-auth.yml override).
# =============================================================================

# ---------------------------------------------------------------------------
# Build Arguments
# ---------------------------------------------------------------------------
ARG BASE_PYTHON_IMAGE=python
ARG BASE_PYTHON_VERSION=3.14-alpine

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM ${BASE_PYTHON_IMAGE}:${BASE_PYTHON_VERSION}

# ---------------------------------------------------------------------------
# Metadata Labels (Legacy)
# ---------------------------------------------------------------------------
LABEL vendor="BAUER GROUP"
LABEL maintainer="Karl Bauer <karl.bauer@bauer-group.com>"

# ---------------------------------------------------------------------------
# OCI Image Spec Labels
# ---------------------------------------------------------------------------
LABEL org.opencontainers.image.title="GitHub Runner Cleanup Manager"
LABEL org.opencontainers.image.description="Scheduled removal of leaked offline self-hosted runner registrations"
LABEL org.opencontainers.image.vendor="BAUER GROUP"
LABEL org.opencontainers.image.authors="Karl Bauer <karl.bauer@bauer-group.com>"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/bauer-group/CI-GitHubRunner"
LABEL org.opencontainers.image.url="https://github.com/bauer-group/CI-GitHubRunner"
LABEL org.opencontainers.image.documentation="https://github.com/bauer-group/CI-GitHubRunner#readme"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ---------------------------------------------------------------------------
# System packages (build-time + runtime split for smaller image)
# ---------------------------------------------------------------------------
# Build deps for cryptography wheel compilation are only needed during
# pip install, then removed. tini stays for proper PID-1 signal handling.
COPY requirements.txt /tmp/requirements.txt
RUN apk add --no-cache tini \
    && apk add --no-cache --virtual .build-deps \
        gcc \
        musl-dev \
        libffi-dev \
        openssl-dev \
        cargo \
        rust \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && apk del .build-deps \
    && rm -rf /var/cache/apk/* /tmp/requirements.txt

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
WORKDIR /app

COPY main.py config.py scheduler.py console.py github_api.py auth.py rate_limit.py ./

# ---------------------------------------------------------------------------
# Non-root user
# ---------------------------------------------------------------------------
RUN addgroup -g 1000 cleanup \
    && adduser -u 1000 -G cleanup -h /app -D cleanup

USER cleanup

# ---------------------------------------------------------------------------
# Entrypoint (tini for proper signal handling)
# ---------------------------------------------------------------------------
ENTRYPOINT ["/sbin/tini", "--", "python", "main.py"]
