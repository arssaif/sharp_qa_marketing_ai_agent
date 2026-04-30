"""APScheduler setup — nightly cron for source + enrich stages."""

from __future__ import annotations

import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler instance.

    Returns:
        The BackgroundScheduler instance.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def setup_nightly_sourcing(settings) -> None:
    """Configure the nightly sourcing job.

    Args:
        settings: Application settings with cron configuration.
    """
    scheduler = get_scheduler()

    def nightly_job():
        """Run source + enrich stages."""
        from sharpqa_agent.orchestrator.pipeline import run_pipeline
        logger.info("nightly_sourcing_started")
        asyncio.run(run_pipeline(["source", "enrich"], limit=50, settings=settings))

    scheduler.add_job(
        nightly_job,
        trigger=CronTrigger(
            hour=settings.nightly_source_cron_hour,
            minute=settings.nightly_source_cron_minute,
        ),
        id="nightly_sourcing",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()
        logger.info(
            "scheduler_started",
            cron=f"{settings.nightly_source_cron_hour}:{settings.nightly_source_cron_minute:02d}",
        )


def shutdown_scheduler() -> None:
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_shutdown")
