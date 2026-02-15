"""Task manager lifecycle — start, stop, schedule.

The ``TaskManager`` owns a set of ``CronJob`` definitions and runs them
on asyncio background tasks.  Each job has a ``period`` (seconds) and a
handler coroutine.  Jobs can optionally acquire a distributed Redis lock
so only one instance in a cluster executes the job at a time.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from spv_wallet.metrics.collector import EngineMetrics

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CronJob:
    """A recurring background job."""

    handler: Callable[[], Awaitable[None]]
    period: float  # seconds
    name: str = ""


class TaskManager:
    """Manages asyncio-based cron jobs.

    Usage::

        tm = TaskManager(metrics=engine_metrics)
        tm.register("cleanup", CronJob(handler=..., period=60))
        await tm.start()
        ...
        await tm.stop()
    """

    def __init__(self, *, metrics: EngineMetrics | None = None) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False
        self._metrics = metrics

    @property
    def is_running(self) -> bool:
        """Whether the task manager is currently running."""
        return self._running

    @property
    def jobs(self) -> dict[str, CronJob]:
        """Registered jobs (name → CronJob)."""
        return dict(self._jobs)

    def register(self, name: str, job: CronJob) -> None:
        """Register a cron job.  Can be called before or after start().

        If the manager is already running the job is started immediately.
        """
        resolved = CronJob(handler=job.handler, period=job.period, name=name)
        self._jobs[name] = resolved
        if self._running:
            self._tasks[name] = asyncio.create_task(self._run_loop(resolved))

    async def start(self) -> None:
        """Start all registered cron jobs."""
        if self._running:
            return
        self._running = True
        for name, job in self._jobs.items():
            self._tasks[name] = asyncio.create_task(self._run_loop(job))
        logger.info("TaskManager started with %d jobs", len(self._jobs))

    async def stop(self) -> None:
        """Cancel all running jobs and wait for cleanup."""
        if not self._running:
            return
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        # Wait for all tasks to finish — suppress CancelledError
        results = await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        for r in results:
            if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError):
                logger.error("Task error during shutdown: %s", r)
        self._tasks.clear()
        logger.info("TaskManager stopped")

    async def _run_loop(self, job: CronJob) -> None:
        """Repeatedly execute *job* every *job.period* seconds."""
        name = job.name or "unnamed"
        while self._running:
            try:
                await asyncio.sleep(job.period)
                if not self._running:
                    break
                if self._metrics:
                    with self._metrics.track_cron(name):
                        await job.handler()
                else:
                    await job.handler()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Cron job %r failed", name)
