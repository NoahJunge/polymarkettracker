"""Scheduler manager — APScheduler integration for collection and export jobs."""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.es_client import ESClient
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)

COLLECTOR_JOB_ID = "collector"
EXPORT_JOB_ID = "daily_export"
DCA_JOB_ID = "dca_daily"


class SchedulerManager:
    def __init__(self, es: ESClient, settings_svc, collector_svc, export_svc, alerts_svc=None, dca_svc=None):
        self.es = es
        self.settings_svc = settings_svc
        self.collector_svc = collector_svc
        self.export_svc = export_svc
        self.alerts_svc = alerts_svc
        self.dca_svc = dca_svc
        self.scheduler = AsyncIOScheduler()
        self._started = False

    async def start(self):
        """Initialize and start the scheduler based on ES settings."""
        settings = await self.settings_svc.get()

        # Collection job
        if settings.collector_enabled:
            if settings.cron_expression:
                trigger = CronTrigger.from_crontab(settings.cron_expression)
            else:
                trigger = IntervalTrigger(minutes=settings.collector_interval_minutes)

            self.scheduler.add_job(
                self._run_collector,
                trigger=trigger,
                id=COLLECTOR_JOB_ID,
                name="Market Collector",
                replace_existing=True,
                misfire_grace_time=120,
            )
            logger.info(
                "Scheduled collector: interval=%dm, cron=%s",
                settings.collector_interval_minutes,
                settings.cron_expression,
            )

        # Daily export job
        if settings.export_enabled:
            self.scheduler.add_job(
                self._run_export,
                trigger=CronTrigger(hour=0, minute=5),
                id=EXPORT_JOB_ID,
                name="Daily Export",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info("Scheduled daily export at 00:05 UTC")

        # DCA daily job
        if self.dca_svc:
            self.scheduler.add_job(
                self._run_dca,
                trigger=CronTrigger(hour=0, minute=30),
                id=DCA_JOB_ID,
                name="DCA Daily Trades",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info("Scheduled DCA daily job at 00:30 UTC")

        self.scheduler.start()
        self._started = True
        logger.info("Scheduler started")

    async def shutdown(self):
        """Shut down the scheduler."""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler shut down")

    async def update_schedule(self):
        """Re-read settings and update job schedules."""
        settings = await self.settings_svc.get()

        if settings.collector_enabled:
            if settings.cron_expression:
                trigger = CronTrigger.from_crontab(settings.cron_expression)
            else:
                trigger = IntervalTrigger(minutes=settings.collector_interval_minutes)

            try:
                self.scheduler.reschedule_job(COLLECTOR_JOB_ID, trigger=trigger)
            except Exception:
                self.scheduler.add_job(
                    self._run_collector,
                    trigger=trigger,
                    id=COLLECTOR_JOB_ID,
                    name="Market Collector",
                    replace_existing=True,
                    misfire_grace_time=120,
                )
            logger.info("Updated collector schedule")
        else:
            try:
                self.scheduler.pause_job(COLLECTOR_JOB_ID)
                logger.info("Paused collector job")
            except Exception:
                pass

    async def run_collector_now(self) -> dict:
        """Trigger an immediate collector run."""
        return await self._run_collector()

    def get_status(self) -> dict:
        """Get scheduler status and job info."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            })

        return {
            "running": self._started,
            "jobs": jobs,
            "last_run_utc": (
                self.collector_svc.last_run_utc.isoformat()
                if self.collector_svc.last_run_utc
                else None
            ),
            "last_run_stats": self.collector_svc.last_run_stats,
            "is_collecting": self.collector_svc.is_running,
        }

    async def _run_collector(self) -> dict:
        """Internal: run the collector, then check alerts."""
        logger.info("Starting collector run")
        result = await self.collector_svc.run()
        # Check price alerts after fresh data is collected
        if self.alerts_svc:
            try:
                triggered = await self.alerts_svc.check_alerts()
                if triggered:
                    logger.info("Triggered %d price alerts", len(triggered))
            except Exception as e:
                logger.error("Alert check failed: %s", e)
        return result

    async def _run_export(self):
        """Internal: run the daily export."""
        logger.info("Starting daily export")
        filepath = await self.export_svc.export_daily_snapshot()
        if filepath:
            logger.info("Daily export completed: %s", filepath)

    async def _run_dca(self):
        """Internal: run daily DCA trades."""
        if not self.dca_svc:
            return
        logger.info("Starting DCA daily execution")
        result = await self.dca_svc.execute_daily()
        logger.info("DCA daily execution complete: %s", result)
