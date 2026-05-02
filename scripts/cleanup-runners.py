#!/usr/bin/env python3
"""
Cleanup Offline GitHub Actions Self-Hosted Runners
==================================================
Removes offline (disconnected) runner registrations from a GitHub
organization or repository. Reads auth/scope config from `../.env` so
it shares the same configuration as runner.sh.

Why this exists:
    Ephemeral runners that register but never run a job (cancelled
    before assignment, OOM-killed mid-startup, force-stopped) leave an
    "offline" registration entry in GitHub. GitHub auto-cleans these
    after ~30 days, which is too slow if you approach the 10k/org
    limit and start losing the ability to register new runners.

Usage:
    python3 scripts/cleanup-runners.py [options]
    ./runner.sh cleanup-runners [options]

Options:
    --dry-run, -n         Preview, no deletions
    --batch N             Cap deletions at N this run (default: all)
    --reserve-pct FRAC    Fraction of rate-limit bucket to leave for gh CLI
                          and other workflows (default: 0.05 = 5%)
    --floor-delay SEC     Minimum seconds between requests, defends against
                          the secondary rate limit. Auto-doubles to max 5s
                          on each 403/429 hit (default: 0.5)
    --min-age-days N      Only delete runners older than N days
    --name-pattern REGEX  Only delete runners whose name matches regex
    --yes, -y             Skip confirmation prompt
    --help, -h            Show help

Pacing strategy (no static rate-delay needed):
    - Proactive: every response carries X-RateLimit-Limit/-Remaining/-Reset.
      The script paces requests to stay above `reserve-pct * limit` quota,
      so concurrent gh CLI usage and workflows never run out of headroom.
    - Reactive: on a secondary-limit response (403/429 + Retry-After),
      the script sleeps the exact Retry-After value, then doubles
      floor-delay so the rest of the run is paced more cautiously.

Auth (from .env, in this priority):
    1. GITHUB_ACCESS_TOKEN (PAT, scope: admin:org or repo)
    2. APP_ID + APP_PRIVATE_KEY_FILE (GitHub App; needs `openssl` CLI)

Scope (from .env):
    ORG_NAME      organization-level runners
    or REPO_URL   repository-level runners

Requirements:
    Python 3.7+, no external pip packages.
    `openssl` CLI required only for GitHub App auth.
"""

import argparse
import base64
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


# ============================================================================
# Output formatting
# ============================================================================

class C:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

    @classmethod
    def disable(cls):
        for k in ('RED', 'GREEN', 'YELLOW', 'BLUE', 'CYAN', 'NC'):
            setattr(cls, k, '')


if not sys.stdout.isatty():
    C.disable()


def info(msg):  print(f"{C.CYAN}i {msg}{C.NC}")
def ok(msg):    print(f"{C.GREEN}+ {msg}{C.NC}")
def warn(msg):  print(f"{C.YELLOW}! {msg}{C.NC}")
def err(msg):   print(f"{C.RED}x {msg}{C.NC}", file=sys.stderr)


# ============================================================================
# .env loader (minimal, no external deps)
# ============================================================================

def load_env(path: Path) -> dict:
    if not path.is_file():
        err(f".env file not found: {path}")
        err("Run scripts/setup-env.sh first or copy .env.example to .env")
        sys.exit(1)
    env = {}
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ============================================================================
# GitHub App JWT + installation token (stdlib + openssl)
# ============================================================================

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def make_jwt(app_id: str, private_key_path: Path) -> str:
    if not private_key_path.is_file():
        err(f"GitHub App private key not found: {private_key_path}")
        sys.exit(1)

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 60, "exp": now + 540, "iss": str(app_id)}
    h = b64url(json.dumps(header, separators=(',', ':')).encode())
    p = b64url(json.dumps(payload, separators=(',', ':')).encode())
    msg = f"{h}.{p}".encode()

    try:
        proc = subprocess.run(
            ['openssl', 'dgst', '-sha256', '-sign', str(private_key_path)],
            input=msg, capture_output=True, check=True,
        )
    except FileNotFoundError:
        err("`openssl` CLI not found. Install openssl, or use PAT auth (set GITHUB_ACCESS_TOKEN).")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        err(f"JWT signing failed: {e.stderr.decode(errors='replace')}")
        sys.exit(1)

    return f"{h}.{p}.{b64url(proc.stdout)}"


def get_installation_token(jwt: str, install_scope: str) -> str:
    inst, _ = api_request(f"https://api.github.com/{install_scope}/installation",
                          jwt, method='GET')
    tok, _ = api_request(f"https://api.github.com/app/installations/{inst['id']}/access_tokens",
                         jwt, method='POST', body=b'')
    return tok['token']


# ============================================================================
# GitHub REST API helpers
# ============================================================================

API_BASE = "https://api.github.com"


def api_request(url: str, token: str, method: str = 'GET', body: bytes = None):
    req = urllib.request.Request(url, method=method, data=body)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('X-GitHub-Api-Version', '2022-11-28')
    req.add_header('User-Agent', 'bauer-group-runner-cleanup')
    if body is not None:
        req.add_header('Content-Length', str(len(body)))
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read()
        headers = dict(resp.headers)
        if not raw:
            return None, headers
        return json.loads(raw), headers
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors='replace')
        # Re-raise with body attached so callers can decide how to react
        e.body_text = body_text  # type: ignore[attr-defined]
        raise


def list_runners(scope: str, token: str, rate: 'RateLimit | None' = None):
    page = 1
    while True:
        url = f"{API_BASE}/{scope}/actions/runners?per_page=100&page={page}"
        data, headers = api_request(url, token, 'GET')
        if rate is not None:
            rate.update(headers)
        runners = (data or {}).get('runners') or []
        if not runners:
            return
        yield from runners
        if len(runners) < 100:
            return
        page += 1


def delete_runner(scope: str, runner_id: int, token: str):
    """Delete one runner.

    Returns: (ok, headers, errmsg, retry_after_sec)
        retry_after_sec is set only when GitHub returns a secondary
        rate-limit response (403/429 with abuse/secondary message).
        Caller should then sleep that long and retry.
    """
    url = f"{API_BASE}/{scope}/actions/runners/{runner_id}"
    try:
        _, headers = api_request(url, token, 'DELETE')
        return True, headers, None, None
    except urllib.error.HTTPError as e:
        headers = dict(e.headers or {})
        body = getattr(e, 'body_text', '') or ''
        retry_after = None
        if e.code in (403, 429):
            body_lower = body.lower()
            if ('secondary rate limit' in body_lower
                    or 'abuse' in body_lower
                    or 'Retry-After' in headers):
                try:
                    retry_after = int(headers.get('Retry-After', '60'))
                except (TypeError, ValueError):
                    retry_after = 60
        errmsg = f"HTTP {e.code}: {body[:120]}"
        return False, headers, errmsg, retry_after


# ============================================================================
# Helpers
# ============================================================================

def parse_iso8601(s: str) -> float:
    if not s:
        return 0.0
    try:
        return datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0.0


def fmt_duration(sec: float) -> str:
    sec = max(int(sec), 0)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m{sec % 60:02d}s"
    return f"{sec // 3600}h{(sec % 3600) // 60:02d}m"


def resolve_pem_path(project_root: Path, raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    if raw.startswith('./'):
        return project_root / raw[2:]
    return project_root / raw


# ============================================================================
# Rate limit state (proactive primary + reactive secondary)
# ============================================================================

class RateLimit:
    """Tracks GitHub rate-limit state and computes the right pacing.

    Two limit dimensions are handled independently:

    1. Primary (proactive). `X-RateLimit-Limit/-Remaining/-Reset` are
       reported on every response. We pace requests so we never drop
       below `reserve_pct` of the bucket -- that headroom is left for
       gh CLI, dashboards, webhooks and other consumers sharing the
       same App installation token.

    2. Secondary (reactive). The "secondary" or "abuse" rate limit is
       a burst-protection layer with no proactive header signal. We
       only learn we hit it when GitHub returns 403/429 with a
       `Retry-After` header. We then sleep that exact duration and
       double `floor_delay` so the rest of the run is paced more
       cautiously. floor_delay never auto-decreases.
    """

    SECONDARY_FLOOR_CAP = 5.0  # never auto-raise floor above 5s

    def __init__(self, reserve_pct: float = 0.05, floor_delay: float = 0.5):
        self.limit = 5000
        self.remaining = 5000
        self.reset_at = int(time.time()) + 3600
        self.reserve_pct = max(0.0, min(reserve_pct, 0.5))
        self.floor_delay = max(0.0, floor_delay)
        self.secondary_hits = 0

    def update(self, headers: dict):
        try:
            self.limit = int(headers.get('X-RateLimit-Limit', self.limit))
            self.remaining = int(headers.get('X-RateLimit-Remaining', self.remaining))
            self.reset_at = int(headers.get('X-RateLimit-Reset', self.reset_at))
        except (TypeError, ValueError):
            pass

    def reserved(self) -> int:
        return int(self.limit * self.reserve_pct)

    def usable(self) -> int:
        return max(0, self.remaining - self.reserved())

    def seconds_to_reset(self) -> int:
        return max(self.reset_at - int(time.time()), 0)

    def proactive_delay(self, candidates_left: int) -> float:
        """How long to sleep before the next request, based on the primary
        bucket. If usable quota is exhausted, returns "wait until reset"."""
        usable = self.usable()
        if usable == 0:
            return float(self.seconds_to_reset() + 2)
        if usable >= candidates_left:
            return self.floor_delay
        # Spread remaining requests evenly across the rest of the window.
        pacing = self.seconds_to_reset() / max(usable, 1)
        return max(pacing, self.floor_delay)

    def react_to_secondary(self, retry_after_sec: int):
        """Called when GitHub returns a 403/429 secondary-limit response."""
        self.secondary_hits += 1
        new_floor = min(max(self.floor_delay * 2, 1.0), self.SECONDARY_FLOOR_CAP)
        self.floor_delay = new_floor

    def quota_summary(self) -> str:
        usable = self.usable()
        pct = (self.remaining / self.limit * 100) if self.limit else 0
        reset_in = fmt_duration(self.seconds_to_reset())
        return (f"quota: {self.remaining}/{self.limit} ({pct:.0f}%, "
                f"reset in {reset_in}, reserve {self.reserved()}, usable {usable})")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog='cleanup-runners.py',
        description="Cleanup offline GitHub Actions self-hosted runners",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help="Preview deletions only")
    parser.add_argument('--batch', type=int, default=0, metavar='N',
                        help="Cap deletions at N this run (default: all)")
    parser.add_argument('--reserve-pct', type=float, default=0.05, metavar='FRAC',
                        help="Fraction of rate-limit bucket to leave for other "
                             "consumers (gh CLI, workflows). Default: 0.05 (5%%)")
    parser.add_argument('--floor-delay', type=float, default=0.5, metavar='SEC',
                        help="Minimum seconds between requests, defends against "
                             "the secondary rate limit. Auto-doubles on each 403/429 "
                             "(capped at 5s). Default: 0.5")
    parser.add_argument('--rate-delay', type=float, default=None, metavar='SEC',
                        help=argparse.SUPPRESS)  # deprecated alias for --floor-delay
    parser.add_argument('--min-age-days', type=int, default=0, metavar='N',
                        help="Only delete runners older than N days")
    parser.add_argument('--name-pattern', type=str, default=None, metavar='REGEX',
                        help="Only delete runners whose name matches this regex")
    parser.add_argument('--yes', '-y', action='store_true',
                        help="Skip interactive confirmation")
    args = parser.parse_args()

    # Back-compat: --rate-delay is now --floor-delay; honor whichever is set
    if args.rate_delay is not None:
        args.floor_delay = args.rate_delay

    project_root = Path(__file__).resolve().parent.parent
    env = load_env(project_root / '.env')

    # ---- Resolve scope (org or repo) ----
    org = env.get('ORG_NAME', '').strip()
    repo_url = env.get('REPO_URL', '').strip()
    if org:
        scope = f"orgs/{org}"
        target = f"organization '{org}'"
        org_for_app_install = org
    elif repo_url:
        m = re.match(r'^https?://github\.com/(.+?)/?$', repo_url)
        if not m:
            err(f"Invalid REPO_URL: {repo_url}")
            sys.exit(1)
        scope = f"repos/{m.group(1)}"
        target = f"repository '{m.group(1)}'"
        org_for_app_install = m.group(1).split('/')[0]
    else:
        err("Neither ORG_NAME nor REPO_URL is set in .env")
        sys.exit(1)

    # ---- Resolve auth ----
    pat = env.get('GITHUB_ACCESS_TOKEN', '').strip()
    is_placeholder_pat = (not pat) or pat.startswith('ghp_xxxxxxxxx')
    app_id = env.get('APP_ID', '').strip()
    pem_file = env.get('APP_PRIVATE_KEY_FILE', '').strip()

    if not is_placeholder_pat:
        token = pat
        auth_label = "PAT (GITHUB_ACCESS_TOKEN)"
    elif app_id and pem_file:
        pem_path = resolve_pem_path(project_root, pem_file)
        info(f"Using GitHub App auth (App ID {app_id})")
        info(f"Private key: {pem_path}")
        jwt = make_jwt(app_id, pem_path)
        # Installation tokens are scoped per installation; for org runners
        # the installation lives at orgs/<org>/installation.
        token = get_installation_token(jwt, f"orgs/{org_for_app_install}")
        auth_label = f"GitHub App {app_id}"
    else:
        err("No valid auth in .env. Set GITHUB_ACCESS_TOKEN (PAT) or APP_ID+APP_PRIVATE_KEY_FILE.")
        sys.exit(1)

    # ---- Initialize rate-limit state ----
    rate = RateLimit(reserve_pct=args.reserve_pct, floor_delay=args.floor_delay)

    # ---- Discovery ----
    info(f"Target: {target}")
    info(f"Auth:   {auth_label}")
    print()
    info("Listing runners (paginated, 100/page)...")
    try:
        all_runners = list(list_runners(scope, token, rate=rate))
    except urllib.error.HTTPError as e:
        err(f"Failed to list runners: HTTP {e.code} - {getattr(e, 'body_text', '')[:200]}")
        sys.exit(1)

    info(f"Initial {rate.quota_summary()}")

    online = [r for r in all_runners if r.get('status') == 'online']
    offline = [r for r in all_runners if r.get('status') == 'offline']
    info(f"Total runners: {len(all_runners)}  (online: {len(online)}, offline: {len(offline)})")

    if not offline:
        ok("Nothing to clean up - no offline runners found")
        return

    # ---- Apply filters ----
    candidates = offline
    if args.min_age_days > 0:
        cutoff = time.time() - args.min_age_days * 86400
        candidates = [r for r in candidates if parse_iso8601(r.get('created_at', '')) < cutoff]
        info(f"After --min-age-days={args.min_age_days}: {len(candidates)} candidates")

    if args.name_pattern:
        try:
            rx = re.compile(args.name_pattern)
        except re.error as e:
            err(f"Invalid --name-pattern regex: {e}")
            sys.exit(1)
        candidates = [r for r in candidates if rx.search(r.get('name', ''))]
        info(f"After --name-pattern: {len(candidates)} candidates")

    if args.batch > 0:
        candidates = candidates[:args.batch]
        info(f"After --batch={args.batch}: {len(candidates)} candidates (this run)")

    if not candidates:
        ok("No runners match the deletion criteria")
        return

    # ---- Preview ----
    print()
    info(f"Sample (first 5 of {len(candidates)}):")
    for r in candidates[:5]:
        print(f"  - {r.get('name', '?'):<40s}  id={r.get('id', '?'):<10}  created={r.get('created_at', '?')}")
    if len(candidates) > 5:
        print(f"  ... and {len(candidates) - 5} more")

    # ---- Estimate runtime ----
    # Best case: floor-delay only (quota was plentiful)
    # Worst case: pace across multiple reset windows when quota is tight
    n = len(candidates)
    best_case = n * rate.floor_delay
    usable_now = rate.usable()
    if usable_now >= n:
        eta_str = f"~{fmt_duration(best_case)} (single window, floor-paced)"
    else:
        # Will need (n - usable_now) extra requests across future windows
        windows_needed = max(1, -(-(n - usable_now) // max(rate.limit - rate.reserved(), 1)))
        worst_case = best_case + windows_needed * 3600
        eta_str = (f"~{fmt_duration(best_case)}-{fmt_duration(worst_case)} "
                   f"(quota will require {windows_needed + 1} reset windows)")
    print()
    info(f"Estimated runtime: {eta_str}")
    info(f"Floor delay: {rate.floor_delay}s   Reserve: {rate.reserve_pct * 100:.0f}% "
         f"({rate.reserved()} requests)")

    if args.dry_run:
        warn("DRY RUN - no deletions performed")
        return

    # ---- Confirm ----
    if not args.yes:
        prompt = f"\n{C.YELLOW}Delete {len(candidates)} offline runners from {target}? Type 'yes' to confirm: {C.NC}"
        try:
            ans = input(prompt).strip().lower()
        except EOFError:
            ans = ''
        if ans != 'yes':
            info("Cancelled")
            return

    # ---- Delete loop ----
    print()
    info(f"Deleting {len(candidates)} runners (adaptive pacing)...")
    deleted = 0
    failed = 0
    start = time.time()

    for i, r in enumerate(candidates, 1):
        rid = r.get('id')
        rname = r.get('name', '?')
        candidates_left = len(candidates) - i + 1

        ok_, headers, errmsg, retry_after = delete_runner(scope, rid, token)
        rate.update(headers)

        # Reactive: secondary rate limit hit -> sleep Retry-After + retry once
        if not ok_ and retry_after is not None:
            warn(f"  Secondary rate limit hit at request {i}. "
                 f"Sleeping {retry_after}s (Retry-After)...")
            rate.react_to_secondary(retry_after)
            time.sleep(retry_after + 1)
            ok_, headers, errmsg, retry_after2 = delete_runner(scope, rid, token)
            rate.update(headers)
            if retry_after2 is not None:
                # Second hit in a row - back off harder, count as failed for now
                rate.react_to_secondary(retry_after2)
                warn(f"  Secondary limit hit again. floor-delay raised to "
                     f"{rate.floor_delay}s, skipping this runner for retry next run.")

        if ok_:
            deleted += 1
        else:
            failed += 1
            warn(f"  failed: {rname} (id={rid}) - {errmsg}")

        # Progress every 50, plus first/last
        if i == 1 or i % 50 == 0 or i == len(candidates):
            elapsed = time.time() - start
            obs_rate = i / elapsed if elapsed > 0 else 0
            eta_remaining = (len(candidates) - i) / obs_rate if obs_rate > 0 else 0
            print(f"  [{i:>5d}/{len(candidates)}] deleted={deleted} failed={failed} "
                  f"({obs_rate:.1f} req/s, ETA {fmt_duration(eta_remaining)}) | {rate.quota_summary()}")
            if rate.secondary_hits > 0:
                print(f"           secondary-hits={rate.secondary_hits}, "
                      f"floor-delay={rate.floor_delay}s")

        # Proactive: pace next request based on primary bucket state
        if i < len(candidates):
            delay = rate.proactive_delay(candidates_left - 1)
            # If we're waiting for reset, surface that to the operator
            if delay > 60:
                warn(f"  Quota at reserve floor ({rate.remaining}/{rate.limit}, "
                     f"reserve {rate.reserved()}). Sleeping {fmt_duration(delay)} "
                     f"until reset to leave headroom for gh CLI / workflows...")
            time.sleep(delay)

    print()
    elapsed = time.time() - start
    if failed:
        warn(f"Done with errors - deleted {deleted}, failed {failed}, total time {fmt_duration(elapsed)}")
        sys.exit(2)
    else:
        ok(f"Done - deleted {deleted} offline runners in {fmt_duration(elapsed)}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print()
        warn("Interrupted - partial progress preserved")
        sys.exit(130)
