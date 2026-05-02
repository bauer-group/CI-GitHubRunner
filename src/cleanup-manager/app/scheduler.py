"""
Cleanup Manager - APScheduler v4 wrapper

Mirrors the BackupScheduler shape from CS-GitHubBackup so the operational
behavior is familiar across the BAUER GROUP container fleet.
"""

import signal
from typing import Callable

from apscheduler import Event, JobReleased, Scheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from config import Settings
from console import cleanup_logger, console, print_scheduler_info


class CleanupScheduler:
    """Drives one cleanup pass per scheduled trigger."""

    def __init__(self, settings: Settings, cleanup_func: Callable[[], bool]):
        self.settings = settings
        self.cleanup_func = cleanup_func
        self.scheduler: Scheduler | None = None

    def _run_cleanup(self) -> None:
        try:
            self.cleanup_func()
        except Exception as e:
            cleanup_logger.error(f"Cleanup execution failed: {e}")
            raise

    def _on_job_event(self, event: Event) -> None:
        if not isinstance(event, JobReleased):
            return
        outcome = event.outcome
        if outcome and outcome.name == "error":
            console.print("[red]Cleanup job failed[/]")
        else:
            cleanup_logger.debug("Cleanup job completed")
        self._print_next_run_time()

    def _print_next_run_time(self) -> None:
        if not self.scheduler:
            return
        try:
            sched = self.scheduler.get_schedule("runner_cleanup")
            if sched and sched.next_fire_time:
                ts = sched.next_fire_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                console.print(f"\n[dim]Next cleanup scheduled for:[/] [cyan]{ts}[/]")
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

        with Scheduler() as scheduler:
            self.scheduler = scheduler

            def signal_handler(signum, _frame):
                signal_name = signal.Signals(signum).name
                cleanup_logger.info(f"Received {signal_name}, stopping scheduler...")
                scheduler.stop()

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            scheduler.subscribe(self._on_job_event, {JobReleased})
            schedule_id = scheduler.add_schedule(
                self._run_cleanup, trigger, id="runner_cleanup"
            )

            try:
                sched = scheduler.get_schedule(schedule_id)
                if sched and sched.next_fire_time:
                    ts = sched.next_fire_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                    console.print(f"[dim]Next cleanup:[/] [cyan]{ts}[/]\n")
            except Exception:
                pass

            try:
                scheduler.run_until_stopped()
            except (KeyboardInterrupt, SystemExit):
                cleanup_logger.debug("Scheduler stopped")


def setup_scheduler(settings: Settings, cleanup_func: Callable[[], bool]) -> CleanupScheduler:
    return CleanupScheduler(settings, cleanup_func)
