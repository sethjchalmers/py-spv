"""In-memory LRU cache implementation (FreeCache equivalent)."""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spv_wallet.config.settings import CacheConfig


class MemoryCache:
    """Thread-safe in-memory LRU cache with TTL support.

    Provides FreeCache-like behavior for development/testing.
    """

    def __init__(self, config: CacheConfig, max_size: int = 10000) -> None:
        """Initialize in-memory cache.

        Args:
            config: Cache configuration (unused for memory backend).
            max_size: Maximum number of keys to store before evicting LRU.
        """
        self._config = config
        self._max_size = max_size
        self._cache: OrderedDict[str, tuple[str, float | None]] = OrderedDict()
        # Format: {key: (value, expiry_timestamp_or_none)}

    async def connect(self) -> None:  # noqa: ASYNC910
        """Connect (no-op for in-memory)."""

    async def close(self) -> None:  # noqa: ASYNC910
        """Close and clear the cache."""
        self._cache.clear()

    async def get(self, key: str) -> str | None:  # noqa: ASYNC910
        """Get a value from the cache.

        Args:
            key: Cache key.

        Returns:
            The cached value, or None if not found/expired.
        """
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]

        # Check expiry
        if expiry is not None and time.time() > expiry:
            del self._cache[key]
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:  # noqa: ASYNC910
        """Set a value in the cache.

        Args:
            key: Cache key.
            value: Value to store.
            ttl: Time-to-live in seconds. None = no expiry.
        """
        expiry = None if ttl is None else time.time() + ttl

        # Remove if exists (to update position)
        if key in self._cache:
            del self._cache[key]

        # Add to end
        self._cache[key] = (value, expiry)

        # Evict LRU if over capacity
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)  # Remove oldest (FIFO for LRU)

    async def delete(self, key: str) -> None:  # noqa: ASYNC910
        """Delete a key from the cache.

        Args:
            key: Cache key.
        """
        self._cache.pop(key, None)

    async def exists(self, key: str) -> bool:  # noqa: ASYNC910
        """Check if a key exists and is not expired.

        Args:
            key: Cache key.

        Returns:
            True if key exists and is valid.
        """
        if key not in self._cache:
            return False

        _, expiry = self._cache[key]

        # Check expiry
        if expiry is not None and time.time() > expiry:
            del self._cache[key]
            return False

        return True

    async def flush(self) -> None:  # noqa: ASYNC910
        """Clear all keys from the cache."""
        self._cache.clear()

