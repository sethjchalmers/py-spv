"""Tests for the TaskManager."""

from __future__ import annotations

import asyncio

import pytest

from spv_wallet.taskmanager.manager import CronJob, TaskManager


class TestCronJob:
    """Tests for CronJob dataclass."""

    def test_frozen(self) -> None:
        async def _handler() -> None:
            pass

        job = CronJob(handler=_handler, period=10.0, name="test")
        assert job.name == "test"
        assert job.period == 10.0

    def test_default_name(self) -> None:
        async def _handler() -> None:
            pass

        job = CronJob(handler=_handler, period=5.0)
        assert job.name == ""


class TestTaskManager:
    """Tests for the TaskManager lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        tm = TaskManager()
        assert not tm.is_running
        await tm.start()
        assert tm.is_running
        await tm.stop()
        assert not tm.is_running

    @pytest.mark.asyncio
    async def test_register_and_jobs(self) -> None:
        counter = {"value": 0}

        async def _handler() -> None:
            counter["value"] += 1

        tm = TaskManager()
        tm.register("test_job", CronJob(handler=_handler, period=0.05))
        assert "test_job" in tm.jobs
        await tm.start()
        # Let it run a few iterations
        await asyncio.sleep(0.2)
        await tm.stop()
        assert counter["value"] >= 1

    @pytest.mark.asyncio
    async def test_register_while_running(self) -> None:
        counter = {"value": 0}

        async def _handler() -> None:
            counter["value"] += 1

        tm = TaskManager()
        await tm.start()
        tm.register("late_job", CronJob(handler=_handler, period=0.05))
        await asyncio.sleep(0.2)
        await tm.stop()
        assert counter["value"] >= 1

    @pytest.mark.asyncio
    async def test_idempotent_start(self) -> None:
        tm = TaskManager()
        await tm.start()
        await tm.start()  # Should not raise
        assert tm.is_running
        await tm.stop()

    @pytest.mark.asyncio
    async def test_idempotent_stop(self) -> None:
        tm = TaskManager()
        await tm.stop()  # Should not raise when not running
        assert not tm.is_running

    @pytest.mark.asyncio
    async def test_error_in_handler_does_not_crash(self) -> None:
        async def _bad_handler() -> None:
            msg = "boom"
            raise ValueError(msg)

        tm = TaskManager()
        tm.register("bad", CronJob(handler=_bad_handler, period=0.05))
        await tm.start()
        await asyncio.sleep(0.15)
        # Should still be running despite errors
        assert tm.is_running
        await tm.stop()
