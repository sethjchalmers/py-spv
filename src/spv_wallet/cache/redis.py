"""Redis cache backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spv_wallet.config.settings import CacheConfig


class RedisCache:
    """Redis-based cache client using redis-py with hiredis parser."""

    def __init__(self, config: CacheConfig) -> None:
        """Initialize Redis cache.

        Args:
            config: Cache configuration with Redis connection details.
        """
        self._config = config
        self._redis = None

    async def connect(self) -> None:
        """Connect to Redis.

        Raises:
            ImportError: If redis package not installed.
            ConnectionError: If Redis connection fails.
        """
        try:
            from redis.asyncio import Redis
        except ImportError as e:
            msg = "redis package not installed. Install with: pip install redis[hiredis]"
            raise ImportError(msg) from e

        # Parse connection details from config
        # Format: redis://host:port/db or redis://user:pass@host:port/db
        self._redis = Redis.from_url(
            self._config.url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=self._config.max_connections,
        )

        # Test connection
        try:
            await self._redis.ping()
        except Exception as e:
            msg = f"Failed to connect to Redis at {self._config.url}"
            raise ConnectionError(msg) from e

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def get(self, key: str) -> str | None:
        """Get a value from Redis.

        Args:
            key: Cache key.

        Returns:
            The cached value, or None if not found.
        """
        assert self._redis is not None
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set a value in Redis.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Time-to-live in seconds. None = no expiry.
        """
        assert self._redis is not None
        if ttl is not None:
            await self._redis.setex(key, ttl, value)
        else:
            await self._redis.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete a key from Redis.

        Args:
            key: Cache key.
        """
        assert self._redis is not None
        await self._redis.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis.

        Args:
            key: Cache key.

        Returns:
            True if the key exists.
        """
        assert self._redis is not None
        result = await self._redis.exists(key)
        return bool(result)

    async def flush(self) -> None:
        """Flush all keys from Redis (use with caution!)."""
        assert self._redis is not None
        await self._redis.flushdb()
