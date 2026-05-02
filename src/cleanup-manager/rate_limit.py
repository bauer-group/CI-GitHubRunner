"""
Cleanup Manager - Rate Limit State

Tracks GitHub's primary and secondary rate limits and computes the
right pacing for delete requests. Same algorithm as
scripts/cleanup-runners.py, extracted to a module for reuse.
"""

import time

from console import fmt_duration


class RateLimit:
    """Two-layer rate-limit handling.

    Primary (proactive): X-RateLimit-Limit/-Remaining/-Reset on every
    response. Used to pace requests so we never drop below
    `reserve_pct * limit` quota - that headroom is left for gh CLI,
    workflows, dashboards and the runner's own registration calls
    sharing the same App-installation token.

    Secondary (reactive): only signaled by 403/429 + Retry-After.
    On hit, sleep that exact duration and double `floor_delay` for
    the rest of the run. floor_delay never auto-decreases.
    """

    SECONDARY_FLOOR_CAP = 5.0

    def __init__(self, reserve_pct: float = 0.10, floor_delay: float = 0.5):
        self.limit = 5000
        self.remaining = 5000
        self.reset_at = int(time.time()) + 3600
        self.reserve_pct = max(0.0, min(reserve_pct, 0.5))
        self.floor_delay = max(0.0, floor_delay)
        self.secondary_hits = 0

    def update(self, headers: dict) -> None:
        try:
            self.limit = int(headers.get("X-RateLimit-Limit", self.limit))
            self.remaining = int(headers.get("X-RateLimit-Remaining", self.remaining))
            self.reset_at = int(headers.get("X-RateLimit-Reset", self.reset_at))
        except (TypeError, ValueError):
            pass

    def reserved(self) -> int:
        return int(self.limit * self.reserve_pct)

    def usable(self) -> int:
        return max(0, self.remaining - self.reserved())

    def seconds_to_reset(self) -> int:
        return max(self.reset_at - int(time.time()), 0)

    def proactive_delay(self, candidates_left: int) -> float:
        """How long to sleep before the next request, based on the primary bucket."""
        usable = self.usable()
        if usable == 0:
            return float(self.seconds_to_reset() + 2)
        if usable >= candidates_left:
            return self.floor_delay
        pacing = self.seconds_to_reset() / max(usable, 1)
        return max(pacing, self.floor_delay)

    def react_to_secondary(self, retry_after_sec: int) -> None:
        self.secondary_hits += 1
        new_floor = min(max(self.floor_delay * 2, 1.0), self.SECONDARY_FLOOR_CAP)
        self.floor_delay = new_floor

    def quota_summary(self) -> str:
        usable = self.usable()
        pct = (self.remaining / self.limit * 100) if self.limit else 0
        return (
            f"quota: {self.remaining}/{self.limit} ({pct:.0f}%, "
            f"reset in {fmt_duration(self.seconds_to_reset())}, "
            f"reserve {self.reserved()}, usable {usable})"
        )
