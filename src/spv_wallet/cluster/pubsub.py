"""Pub/sub backends — Redis and in-memory.

Mirrors Go ``engine/cluster/redis_pubsub.go`` and ``memory_pubsub.go``.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class Channel(enum.StrEnum):
    """Named pub/sub channels matching Go constants."""

    DESTINATION_NEW = "new-destination"


class PubSubService(ABC):
    """Abstract pub/sub service interface."""

    @abstractmethod
    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]) -> None:
        """Subscribe to a channel with a callback."""

    @abstractmethod
    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a channel."""

    @abstractmethod
    async def close(self) -> None:
        """Close the pub/sub connection."""


class MemoryPubSub(PubSubService):
    """In-memory pub/sub for single-instance deployments."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[str], Awaitable[None]]]] = {}

    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]) -> None:
        """Register a callback for a channel."""
        self._subscribers.setdefault(channel, []).append(callback)

    async def publish(self, channel: str, message: str) -> None:
        """Deliver message to all subscribers of the channel."""
        for cb in self._subscribers.get(channel, []):
            try:
                await cb(message)
            except Exception:
                logger.exception("MemoryPubSub callback error on channel %s", channel)

    async def close(self) -> None:
        """Clear all subscribers."""
        self._subscribers.clear()


class RedisPubSub(PubSubService):
    """Redis-backed pub/sub for multi-instance coordination.

    Uses ``redis.asyncio`` pub/sub. Each subscription spawns an asyncio
    task that reads messages from the Redis subscription channel.
    """

    def __init__(self, redis_url: str, *, prefix: str = "bsv_") -> None:
        self._redis_url = redis_url
        self._prefix = prefix
        self._redis: Any = None
        self._pubsub: Any = None
        self._tasks: list[asyncio.Task[None]] = []

    async def _ensure_connection(self) -> None:
        """Lazy-connect to Redis."""
        if self._redis is not None:
            return
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(self._redis_url)
        self._pubsub = self._redis.pubsub()

    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]) -> None:
        """Subscribe to a prefixed Redis channel."""
        await self._ensure_connection()
        full_channel = f"{self._prefix}{channel}"
        await self._pubsub.subscribe(full_channel)

        async def _listener() -> None:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    try:
                        await callback(data)
                    except Exception:
                        logger.exception("RedisPubSub callback error on %s", full_channel)

        task = asyncio.create_task(_listener())
        self._tasks.append(task)

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a prefixed Redis channel."""
        await self._ensure_connection()
        full_channel = f"{self._prefix}{channel}"
        await self._redis.publish(full_channel, message)

    async def close(self) -> None:
        """Close the Redis connection and cancel listener tasks."""
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._pubsub:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis:
            await self._redis.close()
            self._redis = None
