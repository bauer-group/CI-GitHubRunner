"""
Cleanup Manager - GitHub API + Cleanup Logic

Lists organization/repo runners (paginated), filters offline + min-age,
and deletes them via the GitHub API with adaptive pacing.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from auth import resolve_token
from config import Settings
from console import cleanup_logger, console, fmt_duration
from rate_limit import RateLimit


API_BASE = "https://api.github.com"


def _api_request(
    url: str,
    token: str,
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[dict | None, dict, int | None]:
    """Perform a GitHub API request.

    Returns: (data, headers, retry_after_sec)
        retry_after_sec is set only on secondary-rate-limit responses
        (403/429 with abuse/secondary-limit body or Retry-After header).
    """
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
            headers = dict(resp.headers)
            data = json.loads(raw) if raw else None
            return data, headers, None
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        headers = dict(e.headers or {})
        retry_after = None
        if e.code in (403, 429):
            text_lower = body_text.lower()
            if (
                "secondary rate limit" in text_lower
                or "abuse" in text_lower
                or "Retry-After" in headers
            ):
                try:
                    retry_after = int(headers.get("Retry-After", "60"))
                except (TypeError, ValueError):
                    retry_after = 60
        # Wrap the error so callers get structured info but still raise
        e.body_text = body_text  # type: ignore[attr-defined]
        e.retry_after = retry_after  # type: ignore[attr-defined]
        e.gh_headers = headers  # type: ignore[attr-defined]
        raise


def list_runners(scope: str, token: str, rate: RateLimit):
    """Yield all runners in `scope` (paginated 100/page)."""
    page = 1
    while True:
        url = f"{API_BASE}/{scope}/actions/runners?per_page=100&page={page}"
        data, headers, _ = _api_request(url, token, "GET")
        rate.update(headers)
        runners = (data or {}).get("runners") or []
        if not runners:
            return
        yield from runners
        if len(runners) < 100:
            return
        page += 1


def delete_runner(
    scope: str, runner_id: int, token: str
) -> tuple[bool, dict, str | None, int | None]:
    """Delete one runner. Returns (ok, headers, errmsg, retry_after_sec)."""
    url = f"{API_BASE}/{scope}/actions/runners/{runner_id}"
    try:
        _, headers, _ = _api_request(url, token, "DELETE")
        return True, headers, None, None
    except urllib.error.HTTPError as e:
        return (
            False,
            getattr(e, "gh_headers", {}),
            f"HTTP {e.code}: {getattr(e, 'body_text', '')[:120]}",
            getattr(e, "retry_after", None),
        )


def parse_iso8601(s: str) -> float:
    if not s:
        return 0.0
    try:
        return (
            datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
    except ValueError:
        return 0.0


def run_cleanup(settings: Settings) -> bool:
    """Execute one full cleanup pass.

    Returns True on success (zero failures), False otherwise.
    """
    try:
        token, auth_label = resolve_token(settings)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        cleanup_logger.error(f"Auth failed: {e}")
        return False

    try:
        scope = settings.api_scope
    except ValueError as e:
        cleanup_logger.error(str(e))
        return False

    cleanup_logger.info(f"Target: {scope}")
    cleanup_logger.info(f"Auth:   {auth_label}")

    rate = RateLimit(
        reserve_pct=settings.cleanup_reserve_pct,
        floor_delay=settings.cleanup_floor_delay,
    )

    cleanup_logger.status("Listing runners (paginated)...")
    try:
        all_runners = list(list_runners(scope, token, rate))
    except urllib.error.HTTPError as e:
        cleanup_logger.error(
            f"Failed to list runners: HTTP {e.code} - "
            f"{getattr(e, 'body_text', '')[:200]}"
        )
        return False

    online = [r for r in all_runners if r.get("status") == "online"]
    offline = [r for r in all_runners if r.get("status") == "offline"]
    cleanup_logger.info(
        f"Total runners: {len(all_runners)} (online: {len(online)}, offline: {len(offline)})"
    )
    cleanup_logger.info(f"Initial {rate.quota_summary()}")

    if not offline:
        cleanup_logger.success("Nothing to clean up - no offline runners found")
        return True

    # Apply min-age filter
    candidates = offline
    if settings.cleanup_min_age_days > 0:
        cutoff = time.time() - settings.cleanup_min_age_days * 86400
        before = len(candidates)
        candidates = [r for r in candidates if parse_iso8601(r.get("created_at", "")) < cutoff]
        cleanup_logger.info(
            f"After min-age={settings.cleanup_min_age_days}d filter: "
            f"{len(candidates)} candidates (skipped {before - len(candidates)} too-young)"
        )

    if not candidates:
        cleanup_logger.success("No runners match the deletion criteria")
        return True

    cleanup_logger.info(f"Deleting {len(candidates)} runners (adaptive pacing)...")

    deleted = 0
    failed = 0
    start = time.time()

    for i, r in enumerate(candidates, 1):
        rid = r.get("id")
        rname = r.get("name", "?")
        candidates_left = len(candidates) - i + 1

        ok_, headers, errmsg, retry_after = delete_runner(scope, rid, token)
        rate.update(headers)

        # Reactive: secondary rate limit hit -> sleep Retry-After + retry once
        if not ok_ and retry_after is not None:
            cleanup_logger.warning(
                f"Secondary rate limit hit at request {i}. "
                f"Sleeping {retry_after}s (Retry-After)..."
            )
            rate.react_to_secondary(retry_after)
            time.sleep(retry_after + 1)
            ok_, headers, errmsg, retry_after2 = delete_runner(scope, rid, token)
            rate.update(headers)
            if retry_after2 is not None:
                rate.react_to_secondary(retry_after2)
                cleanup_logger.warning(
                    f"Secondary limit hit again. floor-delay raised to "
                    f"{rate.floor_delay}s, will retry runner {rname} next run."
                )

        if ok_:
            deleted += 1
        else:
            failed += 1
            cleanup_logger.warning(f"  failed: {rname} (id={rid}) - {errmsg}")

        # Progress every 50 + first/last
        if i == 1 or i % 50 == 0 or i == len(candidates):
            elapsed = time.time() - start
            obs_rate = i / elapsed if elapsed > 0 else 0
            eta = (len(candidates) - i) / obs_rate if obs_rate > 0 else 0
            console.print(
                f"  [{i:>5d}/{len(candidates)}] deleted={deleted} failed={failed} "
                f"({obs_rate:.1f} req/s, ETA {fmt_duration(eta)}) | {rate.quota_summary()}"
            )
            if rate.secondary_hits > 0:
                console.print(
                    f"           secondary-hits={rate.secondary_hits}, "
                    f"floor-delay={rate.floor_delay}s"
                )

        # Proactive: pace next request based on bucket state
        if i < len(candidates):
            delay = rate.proactive_delay(candidates_left - 1)
            if delay > 60:
                cleanup_logger.warning(
                    f"  Quota at reserve floor ({rate.remaining}/{rate.limit}, "
                    f"reserve {rate.reserved()}). Sleeping {fmt_duration(delay)} "
                    f"until reset to leave headroom for other consumers..."
                )
            time.sleep(delay)

    elapsed = time.time() - start
    if failed:
        cleanup_logger.warning(
            f"Done with errors - deleted {deleted}, failed {failed}, "
            f"total time {fmt_duration(elapsed)}"
        )
        return False

    cleanup_logger.success(
        f"Done - deleted {deleted} offline runners in {fmt_duration(elapsed)}"
    )
    return True
