"""Scheduled downloads worker."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from ..config import get_settings
from .job_store import get_job_store
from .queue_manager import get_queue_manager

logger = logging.getLogger(__name__)


class SchedulerWorker:
    """
    Background worker that triggers scheduled jobs.

    Periodically checks for jobs with scheduled_at times that have passed
    and adds them to the priority queue for processing.
    """

    def __init__(self, check_interval: Optional[int] = None):
        settings = get_settings()
        self._check_interval = check_interval or settings.scheduler_check_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the scheduler worker."""
        settings = get_settings()

        if not settings.scheduler_enabled:
            logger.info("Scheduler is disabled")
            return

        if self._running:
            logger.warning("Scheduler worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Scheduler worker started (interval: {self._check_interval}s)")

    async def stop(self) -> None:
        """Stop the scheduler worker."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Scheduler worker stopped")

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await self._check_scheduled_jobs()
            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            await asyncio.sleep(self._check_interval)

    async def _check_scheduled_jobs(self) -> None:
        """Check for and enqueue scheduled jobs that are due."""
        job_store = get_job_store()
        queue_manager = get_queue_manager()

        # Get jobs that are due
        now = datetime.utcnow().isoformat()
        scheduled_jobs = job_store.get_scheduled_jobs(before_time=now)

        if not scheduled_jobs:
            return

        logger.info(f"Found {len(scheduled_jobs)} scheduled jobs ready to process")

        for job in scheduled_jobs:
            job_id = job["job_id"]
            priority = job.get("priority", 5)

            try:
                # Clear the scheduled_at field
                job_store.clear_scheduled_at(job_id)

                # Add to priority queue
                await queue_manager.enqueue(job_id, priority)

                logger.info(f"Enqueued scheduled job {job_id}")

            except Exception as e:
                logger.error(f"Failed to enqueue scheduled job {job_id}: {e}")


# Global instance
_scheduler_worker: Optional[SchedulerWorker] = None


def get_scheduler_worker() -> SchedulerWorker:
    """Get or create the global scheduler worker instance."""
    global _scheduler_worker
    if _scheduler_worker is None:
        _scheduler_worker = SchedulerWorker()
    return _scheduler_worker


async def start_scheduler_worker() -> None:
    """Start the global scheduler worker."""
    worker = get_scheduler_worker()
    await worker.start()


async def stop_scheduler_worker() -> None:
    """Stop the global scheduler worker."""
    global _scheduler_worker
    if _scheduler_worker:
        await _scheduler_worker.stop()
        _scheduler_worker = None
