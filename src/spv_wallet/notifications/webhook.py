"""Webhook delivery — reliable dispatch with retries.

Mirrors Go ``engine/notifications/webhook_notifier.go`` and
``engine/notifications/webhook_manager.go``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from spv_wallet.notifications.events import RawEvent

logger = logging.getLogger(__name__)

# Constants matching Go implementation
MAX_BATCH_SIZE = 100
MAX_RETRIES = 2
RETRY_DELAY = 1.0  # seconds
BAN_TIME = 3600  # 60 minutes in seconds
CHANNEL_BUFFER = 100


@dataclass
class WebhookConfig:
    """Configuration for a single webhook subscription."""

    url: str
    token_header: str = "Authorization"  # noqa: S105
    token_value: str = ""
    banned_until: float = 0.0  # unix timestamp


class WebhookNotifier:
    """Delivers batched events to a single webhook URL with retries.

    Mirrors Go ``WebhookNotifier``.
    """

    def __init__(self, config: WebhookConfig) -> None:
        self._config = config
        self._queue: asyncio.Queue[RawEvent] = asyncio.Queue(maxsize=CHANNEL_BUFFER)
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._client: httpx.AsyncClient | None = None

    @property
    def url(self) -> str:
        """Return the webhook URL."""
        return self._config.url

    @property
    def is_banned(self) -> bool:
        """Whether the webhook is currently banned."""
        return time.time() < self._config.banned_until

    async def start(self) -> None:
        """Start the consumer loop."""
        if self._running:
            return
        self._running = True
        self._client = httpx.AsyncClient(timeout=10.0)
        self._task = asyncio.create_task(self._consumer())

    async def stop(self) -> None:
        """Stop the consumer and close the HTTP client."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None

    def enqueue(self, event: RawEvent) -> None:
        """Add an event to the delivery queue (non-blocking)."""
        if self.is_banned:
            return
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Webhook queue full for %s — dropping event", self._config.url)

    async def _consumer(self) -> None:
        """Read events and send them in batches."""
        while self._running:
            try:
                # Wait for at least one event
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                batch = [event.to_dict()]
                # Accumulate more events (up to MAX_BATCH_SIZE)
                while len(batch) < MAX_BATCH_SIZE:
                    try:
                        ev = self._queue.get_nowait()
                        batch.append(ev.to_dict())
                    except asyncio.QueueEmpty:
                        break
                await self._send(batch)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Webhook consumer error for %s", self._config.url)

    async def _send(self, events: list[dict[str, Any]]) -> None:
        """Send a batch of events to the webhook URL with retries."""
        if not self._client:
            return

        headers: dict[str, str] = {}
        if self._config.token_header and self._config.token_value:
            headers[self._config.token_header] = self._config.token_value

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.post(
                    self._config.url,
                    json={"events": events},
                    headers=headers,
                )
                if resp.status_code < 400:
                    return
                logger.warning(
                    "Webhook %s returned %d (attempt %d/%d)",
                    self._config.url,
                    resp.status_code,
                    attempt + 1,
                    MAX_RETRIES + 1,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "Webhook %s error: %s (attempt %d/%d)",
                    self._config.url,
                    exc,
                    attempt + 1,
                    MAX_RETRIES + 1,
                )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

        # All retries exhausted — ban the webhook
        self._config.banned_until = time.time() + BAN_TIME
        logger.warning("Webhook %s banned for %d seconds", self._config.url, BAN_TIME)


class WebhookManager:
    """Manages lifecycle of all webhook notifiers.

    Mirrors Go ``WebhookManager``: syncs notifiers with the database,
    subscribes to the notification service for event fan-out.
    """

    def __init__(self) -> None:
        self._notifiers: dict[str, WebhookNotifier] = {}
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether the manager is running."""
        return self._running

    async def start(self) -> None:
        """Start the manager."""
        self._running = True

    async def stop(self) -> None:
        """Stop all notifiers and clean up."""
        self._running = False
        for notifier in self._notifiers.values():
            await notifier.stop()
        self._notifiers.clear()

    async def subscribe(
        self,
        url: str,
        token_header: str = "Authorization",  # noqa: S107
        token_value: str = "",
    ) -> None:
        """Add or update a webhook subscription."""
        if url in self._notifiers:
            await self._notifiers[url].stop()
        config = WebhookConfig(url=url, token_header=token_header, token_value=token_value)
        notifier = WebhookNotifier(config)
        self._notifiers[url] = notifier
        await notifier.start()
        logger.info("Webhook subscribed: %s", url)

    async def unsubscribe(self, url: str) -> None:
        """Remove a webhook subscription."""
        notifier = self._notifiers.pop(url, None)
        if notifier:
            await notifier.stop()
            logger.info("Webhook unsubscribed: %s", url)

    def get_all(self) -> list[dict[str, str]]:
        """Return all registered webhook URLs and their status."""
        return [
            {
                "url": n.url,
                "banned": str(n.is_banned),
            }
            for n in self._notifiers.values()
        ]

    def dispatch(self, event: RawEvent) -> None:
        """Send an event to all active (non-banned) notifiers."""
        for notifier in self._notifiers.values():
            notifier.enqueue(event)
