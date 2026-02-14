"""Cache client abstraction with Redis and in-memory backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from spv_wallet.config.settings import CacheConfig


class CacheClient:
    """Cache abstraction that delegates to Redis or in-memory LRU backend."""

    def __init__(self, config: CacheConfig) -> None:
        """Initialize cache client with configuration.

        Args:
            config: Cache configuration with engine type and connection params.
        """
        self._config = config
        self._backend: CacheBackend | None = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to the cache backend.

        Raises:
            ValueError: If cache engine type is invalid.
        """
        from spv_wallet.cache.memory import MemoryCache
        from spv_wallet.cache.redis import RedisCache

        engine = self._config.engine.lower()

        if engine == "redis":
            self._backend = RedisCache(self._config)
        elif engine in ("freecache", "memory"):
            self._backend = MemoryCache(self._config)
        else:
            msg = f"Unsupported cache engine: {engine}"
            raise ValueError(msg)

        await self._backend.connect()
        self._connected = True

    async def close(self) -> None:
        """Close the cache connection (idempotent)."""
        if self._backend is not None:
            await self._backend.close()
            self._backend = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if the cache is connected."""
        return self._connected and self._backend is not None

    async def get(self, key: str) -> str | None:
        """Get a value from the cache.

        Args:
            key: Cache key.

        Returns:
            The cached value as a string, or None if not found.

        Raises:
            RuntimeError: If not connected.
        """
        self._ensure_connected()
        assert self._backend is not None
        return await self._backend.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key.
            value: Value to store (string).
            ttl: Time-to-live in seconds. None = no expiry.

        Raises:
            RuntimeError: If not connected.
        """
        self._ensure_connected()
        assert self._backend is not None
        await self._backend.set(key, value, ttl=ttl)

    async def delete(self, key: str) -> None:
        """Delete a key from the cache.

        Args:
            key: Cache key.

        Raises:
            RuntimeError: If not connected.
        """
        self._ensure_connected()
        assert self._backend is not None
        await self._backend.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: Cache key.

        Returns:
            True if the key exists, False otherwise.

        Raises:
            RuntimeError: If not connected.
        """
        self._ensure_connected()
        assert self._backend is not None
        return await self._backend.exists(key)

    async def flush(self) -> None:
        """Flush all keys from the cache (development/testing only).

        Raises:
            RuntimeError: If not connected.
        """
        self._ensure_connected()
        assert self._backend is not None
        await self._backend.flush()

    def _ensure_connected(self) -> None:
        """Raise RuntimeError if not connected."""
        if not self._connected or self._backend is None:
            msg = "Cache not connected. Call connect() first."
            raise RuntimeError(msg)


class CacheBackend(Protocol):
    """Protocol for cache backend implementations."""

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def flush(self) -> None: ...
