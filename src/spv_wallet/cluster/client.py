"""Cluster client — factory for pub/sub and distributed locking.

Mirrors Go ``engine/cluster/client.go``.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from spv_wallet.cluster.pubsub import PubSubService

logger = logging.getLogger(__name__)


class Coordinator(enum.StrEnum):
    """Cluster coordinator backend."""

    MEMORY = "memory"
    REDIS = "redis"


class ClusterClient:
    """Factory / lifecycle wrapper for the cluster pub/sub backend.

    Usage::

        cluster = ClusterClient(coordinator=Coordinator.MEMORY)
        await cluster.connect()
        await cluster.pubsub.publish("chan", "msg")
        await cluster.close()
    """

    def __init__(
        self,
        *,
        coordinator: Coordinator | str = Coordinator.MEMORY,
        redis_url: str = "",
        prefix: str = "bsv_",
    ) -> None:
        self._coordinator = (
            Coordinator(coordinator) if isinstance(coordinator, str) else coordinator
        )
        self._redis_url = redis_url
        self._prefix = prefix
        self._pubsub: PubSubService | None = None
        self._redis: Any = None

    @property
    def pubsub(self) -> PubSubService:
        """Return the pub/sub service (must call connect first)."""
        if self._pubsub is None:
            msg = "ClusterClient not connected"
            raise RuntimeError(msg)
        return self._pubsub

    async def connect(self) -> None:
        """Create the pub/sub backend based on coordinator type."""
        if self._pubsub is not None:
            return

        if self._coordinator == Coordinator.REDIS:
            from spv_wallet.cluster.pubsub import RedisPubSub

            self._pubsub = RedisPubSub(self._redis_url, prefix=self._prefix)
            logger.info("Cluster using Redis pub/sub (%s)", self._redis_url)
        else:
            from spv_wallet.cluster.pubsub import MemoryPubSub

            self._pubsub = MemoryPubSub()
            logger.info("Cluster using in-memory pub/sub")

    async def close(self) -> None:
        """Close the pub/sub backend."""
        if self._pubsub is not None:
            await self._pubsub.close()
            self._pubsub = None

    async def try_lock(self, key: str, ttl: int = 60) -> bool:
        """Attempt to acquire a distributed lock via Redis SET NX.

        Returns True if the lock was acquired, False otherwise.
        Falls back to always-True for memory coordinator (single-instance).
        """
        if self._coordinator == Coordinator.MEMORY:
            return True

        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(self._redis_url)

        lock_key = f"{self._prefix}lock:{key}"
        result = await self._redis.set(lock_key, "1", nx=True, ex=ttl)
        return result is not None
