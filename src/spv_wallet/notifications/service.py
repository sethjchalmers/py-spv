"""Notification service — emit events to subscribers.

Fan-out architecture: one input queue → many output queues.
Mirrors Go ``engine/notifications/notifications.go``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spv_wallet.notifications.events import RawEvent

logger = logging.getLogger(__name__)

_INPUT_BUFFER = 100


class NotificationService:
    """Asyncio-based notification fan-out service.

    Usage::

        svc = NotificationService()
        q = svc.add_subscriber("my-sub")
        await svc.start()
        await svc.notify(RawEvent(type="test", content={"k": "v"}))
        event = await q.get()
        await svc.stop()
    """

    def __init__(self) -> None:
        self._input: asyncio.Queue[RawEvent] = asyncio.Queue(maxsize=_INPUT_BUFFER)
        self._subscribers: dict[str, asyncio.Queue[RawEvent]] = {}
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the exchange loop is running."""
        return self._running

    def add_subscriber(self, key: str, *, buffer: int = _INPUT_BUFFER) -> asyncio.Queue[RawEvent]:
        """Register a subscriber and return its output queue."""
        q: asyncio.Queue[RawEvent] = asyncio.Queue(maxsize=buffer)
        self._subscribers[key] = q
        return q

    def remove_subscriber(self, key: str) -> None:
        """Unregister a subscriber."""
        self._subscribers.pop(key, None)

    async def notify(self, event: RawEvent) -> None:
        """Enqueue an event for fan-out to all subscribers."""
        try:
            self._input.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Notification input queue full — dropping event %s", event.type)

    async def start(self) -> None:
        """Start the exchange loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._exchange())

    async def stop(self) -> None:
        """Stop the exchange loop."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _exchange(self) -> None:
        """Read events from input and fan-out to all subscribers."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._input.get(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            for key, q in list(self._subscribers.items()):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("Subscriber %s queue full — dropping event", key)
