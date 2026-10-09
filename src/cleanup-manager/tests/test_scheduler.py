"""Tests for the cleanup scheduler (APScheduler 3)."""

import faulthandler
import os
import signal
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.schedulers.base import STATE_RUNNING
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import scheduler as scheduler_module
from config import Settings
from scheduler import JOB_ID, CleanupScheduler

# A Sunday, after the 04:00 cleanup time used below
SUNDAY_NOON = datetime(2026, 1, 4, 12, 0)

TIMEOUT = 30.0


def make_scheduler(cleanup_func=lambda: True, **overrides) -> CleanupScheduler:
    """Build a CleanupScheduler from real settings, ignoring any .env file."""
    settings = Settings(_env_file=None, **overrides)
    return CleanupScheduler(settings, cleanup_func)


@pytest.fixture
def lifecycle(monkeypatch):
    """Fast polling plus a hang guard for tests that run the scheduler.

    If the scheduler deadlocks on shutdown, faulthandler dumps the stacks
    and exits instead of hanging the build.
    """
    monkeypatch.setattr(scheduler_module, "POLL_INTERVAL_SECONDS", 0.01)
    original = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    faulthandler.dump_traceback_later(120, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
        restored = {sig: signal.getsignal(sig) for sig in original}
        for sig, handler in original.items():
            signal.signal(sig, handler)

    # start() must hand the signal handlers back when it returns
    assert restored == original


def scheduler_is_running(cleanup_scheduler: CleanupScheduler) -> bool:
    sched = cleanup_scheduler.scheduler
    return sched is not None and sched.state == STATE_RUNNING


def run_until_sigterm(cleanup_scheduler, ready, before_stop=None) -> None:
    """Run start() on the main thread and send SIGTERM once ``ready()`` holds.

    ``before_stop`` runs on the helper thread while the scheduler is still
    running; once stopped, APScheduler 3 only looks up pending jobs.
    """

    def stopper():
        deadline = time.monotonic() + TIMEOUT
        while not ready() and time.monotonic() < deadline:
            time.sleep(0.01)
        try:
            if before_stop:
                before_stop()
        finally:
            os.kill(os.getpid(), signal.SIGTERM)

    thread = threading.Thread(target=stopper, daemon=True)
    thread.start()
    cleanup_scheduler.start()
    thread.join(TIMEOUT)


class TestTriggers:
    """Verify the triggers built from the schedule settings."""

    @pytest.mark.parametrize(
        ("day_of_week", "expected_weekdays"),
        [
            ("0", [0]),
            ("6", [6]),
            ("0,3", [0, 3]),
            ("*", [0, 1, 2, 3, 4, 5, 6]),
        ],
    )
    def test_numeric_weekdays_follow_documented_mapping(
        self, day_of_week, expected_weekdays
    ) -> None:
        """Regression: APScheduler 4.0.0a6 read numeric weekdays crontab-style
        (0 = Sunday), so the default "6" (documented as Sunday) fired on
        Saturday. The settings document 0 = Monday ... 6 = Sunday, which the
        3.x trigger honours.
        """
        cleanup_scheduler = make_scheduler(
            cleanup_schedule_day_of_week=day_of_week,
            cleanup_schedule_hour=4,
            cleanup_schedule_minute=0,
        )
        trigger = cleanup_scheduler._create_trigger()
        assert isinstance(trigger, CronTrigger)

        now = SUNDAY_NOON.replace(tzinfo=trigger.timezone)
        fire_times = []
        for _ in expected_weekdays:
            now = trigger.get_next_fire_time(None, now)
            fire_times.append(now)
            now += timedelta(minutes=1)

        assert [fire.weekday() for fire in fire_times] == expected_weekdays
        assert all((fire.hour, fire.minute) == (4, 0) for fire in fire_times)

    def test_default_schedule_description_matches_trigger(self) -> None:
        cleanup_scheduler = make_scheduler()
        trigger = cleanup_scheduler._create_trigger()

        now = SUNDAY_NOON.replace(tzinfo=trigger.timezone)
        assert trigger.get_next_fire_time(None, now).weekday() == 6
        assert cleanup_scheduler._describe_schedule() == "Weekly on Sun at 04:00"

    def test_interval_mode_uses_configured_hours(self) -> None:
        cleanup_scheduler = make_scheduler(
            cleanup_schedule_mode="interval",
            cleanup_schedule_interval_hours=6,
        )
        trigger = cleanup_scheduler._create_trigger()

        assert isinstance(trigger, IntervalTrigger)
        assert trigger.interval == timedelta(hours=6)


class TestLifecycle:
    """Run the scheduler for real and stop it the way Docker does (SIGTERM)."""

    def test_disabled_schedule_returns_without_running(self, lifecycle) -> None:
        calls = []
        cleanup_scheduler = make_scheduler(
            lambda: calls.append(1) or True,
            cleanup_schedule_enabled=False,
            cleanup_run_on_startup=True,
        )

        cleanup_scheduler.start()

        assert calls == []
        assert cleanup_scheduler.scheduler is None

    def test_cron_mode_waits_for_next_fire_time(self, lifecycle) -> None:
        calls = []
        cleanup_scheduler = make_scheduler(lambda: calls.append(1) or True)
        started_at = datetime.now(timezone.utc)
        next_runs = []

        run_until_sigterm(
            cleanup_scheduler,
            lambda: scheduler_is_running(cleanup_scheduler),
            before_stop=lambda: next_runs.append(
                cleanup_scheduler.scheduler.get_job(JOB_ID).next_run_time
            ),
        )

        assert calls == []
        assert len(next_runs) == 1
        assert next_runs[0] > started_at
        assert next_runs[0].weekday() == 6
        assert (next_runs[0].hour, next_runs[0].minute) == (4, 0)
        assert not cleanup_scheduler.scheduler.running

    def test_run_on_startup_runs_once_before_schedule(self, lifecycle) -> None:
        calls = []
        cleanup_scheduler = make_scheduler(
            lambda: calls.append(1) or True,
            cleanup_run_on_startup=True,
        )

        run_until_sigterm(
            cleanup_scheduler, lambda: scheduler_is_running(cleanup_scheduler)
        )

        assert calls == [1]

    def test_interval_mode_runs_first_pass_immediately(self, lifecycle) -> None:
        ran = threading.Event()

        def cleanup() -> bool:
            ran.set()
            return True

        cleanup_scheduler = make_scheduler(
            cleanup,
            cleanup_schedule_mode="interval",
            cleanup_schedule_interval_hours=1,
        )
        started_at = datetime.now(timezone.utc)
        next_runs = []

        # The scheduler moves the job to its next run under the job store
        # lock before releasing it, so this read sees the updated time
        run_until_sigterm(
            cleanup_scheduler,
            ran.is_set,
            before_stop=lambda: next_runs.append(
                cleanup_scheduler.scheduler.get_job(JOB_ID).next_run_time
            ),
        )

        assert ran.is_set()
        assert len(next_runs) == 1
        assert timedelta(minutes=59) < next_runs[0] - started_at < timedelta(minutes=61)
        assert not cleanup_scheduler.scheduler.running

    def test_shutdown_waits_for_running_pass(self, lifecycle) -> None:
        """Regression: shutdown(wait=True) holds the job store lock while it
        waits for the running job, so a job listener that reads the schedule
        would deadlock. The pass must finish and start() must return.
        """
        started = threading.Event()
        finished = threading.Event()

        def cleanup() -> bool:
            started.set()
            # Keep running until shutdown has begun
            while cleanup_scheduler.scheduler.running:
                time.sleep(0.01)
            finished.set()
            return True

        cleanup_scheduler = make_scheduler(cleanup, cleanup_schedule_mode="interval")

        run_until_sigterm(cleanup_scheduler, started.is_set)

        assert finished.is_set()
        assert cleanup_scheduler._job_finished.is_set()

    def test_failed_pass_keeps_schedule(self, lifecycle) -> None:
        def cleanup() -> bool:
            raise RuntimeError("simulated cleanup failure")

        cleanup_scheduler = make_scheduler(cleanup, cleanup_schedule_mode="interval")

        # Record what the job listener receives
        events = []
        on_job_event = cleanup_scheduler._on_job_event

        def record(event) -> None:
            events.append(event)
            on_job_event(event)

        cleanup_scheduler._on_job_event = record
        next_runs = []

        run_until_sigterm(
            cleanup_scheduler,
            lambda: bool(events),
            before_stop=lambda: next_runs.append(
                cleanup_scheduler.scheduler.get_job(JOB_ID).next_run_time
            ),
        )

        assert len(events) == 1
        assert isinstance(events[0].exception, RuntimeError)
        # The failure is reported, the job stays scheduled
        assert next_runs and next_runs[0] is not None
