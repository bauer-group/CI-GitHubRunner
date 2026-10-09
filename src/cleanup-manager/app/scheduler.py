"""
Cleanup Manager - APScheduler 3 wrapper

Mirrors the BackupScheduler shape from CS-GitHubBackup so the operational
behavior is familiar across the BAUER GROUP container fleet.
"""

import signal
import threading
import time
from datetime import datetime
from typing import Callable

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import Settings
from console import cleanup_logger, console, print_scheduler_info

JOB_ID = "runner_cleanup"

# How often the main thread checks for a shutdown request
POLL_INTERVAL_SECONDS = 1.0


class CleanupScheduler:
    """Drives one cleanup pass per scheduled trigger."""

    def __init__(self, settings: Settings, cleanup_func: Callable[[], bool]):
        self.settings = settings
        self.cleanup_func = cleanup_func
        self.scheduler: BackgroundScheduler | None = None
        self._job_finished = threading.Event()
        self._stop_requested = False

    def _run_cleanup(self) -> None:
        try:
            self.cleanup_func()
        except Exception as e:
            cleanup_logger.error(f"Cleanup execution failed: {e}")
            raise

    def _on_job_event(self, event: JobExecutionEvent) -> None:
        # Runs in the executor's worker thread. It must not call back into
        # the scheduler: shutdown() holds the job store lock while it waits
        # for this thread, so a get_job() here would deadlock. The main loop
        # prints the next run time instead.
        if event.exception:
            console.print("[red]Cleanup job failed[/]")
        else:
            cleanup_logger.debug("Cleanup job completed")
        self._job_finished.set()

    def _next_run_time(self) -> datetime | None:
        if not self.scheduler:
            return None
        job = self.scheduler.get_job(JOB_ID)
        return getattr(job, "next_run_time", None) if job else None

    def _print_next_run_time(self, template: str) -> None:
        try:
            next_run_time = self._next_run_time()
            if next_run_time:
                ts = next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                console.print(template.format(ts=ts))
        except Exception as e:
            cleanup_logger.debug(f"Could not read next run time: {e}")

    def _create_trigger(self):
        s = self.settings
        if s.cleanup_schedule_mode == "interval":
            return IntervalTrigger(hours=s.cleanup_schedule_interval_hours)
        return CronTrigger(
            day_of_week=s.cleanup_schedule_day_of_week,
            hour=s.cleanup_schedule_hour,
            minute=s.cleanup_schedule_minute,
        )

    def _describe_schedule(self) -> str:
        s = self.settings
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if s.cleanup_schedule_mode == "interval":
            h = s.cleanup_schedule_interval_hours
            return "Every hour" if h == 1 else f"Every {h} hours"
        if s.cleanup_schedule_day_of_week == "*":
            return f"Daily at {s.cleanup_schedule_hour:02d}:{s.cleanup_schedule_minute:02d}"
        days = [day_names[int(d.strip())] for d in s.cleanup_schedule_day_of_week.split(",")]
        if len(days) == 1:
            return f"Weekly on {days[0]} at {s.cleanup_schedule_hour:02d}:{s.cleanup_schedule_minute:02d}"
        return f"On {', '.join(days)} at {s.cleanup_schedule_hour:02d}:{s.cleanup_schedule_minute:02d}"

    def start(self) -> None:
        if not self.settings.cleanup_schedule_enabled:
            cleanup_logger.warning("Scheduler is disabled (CLEANUP_SCHEDULE_ENABLED=false)")
            return

        # Optional: run immediately on startup before entering the schedule loop
        if self.settings.cleanup_run_on_startup:
            cleanup_logger.info("CLEANUP_RUN_ON_STARTUP=true - running immediate pass")
            try:
                self._run_cleanup()
            except Exception as e:
                cleanup_logger.error(f"Startup cleanup failed: {e}")

        trigger = self._create_trigger()
        print_scheduler_info(self._describe_schedule())

        scheduler = BackgroundScheduler()
        self.scheduler = scheduler
        self._stop_requested = False
        self._job_finished.clear()

        scheduler.add_listener(self._on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

        # Interval schedules run once right away, then every N hours (the
        # APScheduler 4 behaviour this service was built on; 3.x would wait
        # one full interval first)
        first_run = {}
        if self.settings.cleanup_schedule_mode == "interval":
            first_run["next_run_time"] = datetime.now(scheduler.timezone)

        # One pass at a time; a late pass still starts and missed passes
        # collapse into one (the APScheduler 4 defaults)
        scheduler.add_job(
            self._run_cleanup,
            trigger,
            id=JOB_ID,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=None,
            **first_run,
        )

        # Start paused so the next run time is known before the first pass runs
        scheduler.start(paused=True)

        previous_handlers = {
            sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)
        }

        def signal_handler(signum, _frame):
            signal_name = signal.Signals(signum).name
            cleanup_logger.info(f"Received {signal_name}, stopping scheduler...")
            # Only set a flag; the loop below shuts the scheduler down, so
            # the handler never waits on a lock held by this thread
            self._stop_requested = True

        try:
            for sig in previous_handlers:
                signal.signal(sig, signal_handler)

            self._print_next_run_time("[dim]Next cleanup:[/] [cyan]{ts}[/]\n")
            scheduler.resume()

            while not self._stop_requested:
                time.sleep(POLL_INTERVAL_SECONDS)
                if self._job_finished.is_set():
                    self._job_finished.clear()
                    self._print_next_run_time(
                        "\n[dim]Next cleanup scheduled for:[/] [cyan]{ts}[/]"
                    )
        finally:
            # Lets a running cleanup pass finish (capped by the container's
            # stop grace period)
            scheduler.shutdown(wait=True)
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
            cleanup_logger.debug("Scheduler stopped")


def setup_scheduler(settings: Settings, cleanup_func: Callable[[], bool]) -> CleanupScheduler:
    return CleanupScheduler(settings, cleanup_func)
