"""Tests for in-memory LRU cache backend."""

from __future__ import annotations

import asyncio

from spv_wallet.cache.memory import MemoryCache
from spv_wallet.config.settings import CacheConfig, CacheEngine


class TestMemoryCache:
    """Test in-memory LRU cache with TTL."""

    async def test_init(self) -> None:
        """MemoryCache can be instantiated."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config, max_size=100)
        assert cache._max_size == 100
        assert len(cache._cache) == 0

    async def test_connect_close(self) -> None:
        """connect() and close() are no-ops."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)

        await cache.connect()
        await cache.close()
        # Should not raise

    async def test_set_get(self) -> None:
        """Set and get values."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        await cache.set("key1", "value1")
        assert await cache.get("key1") == "value1"

    async def test_get_nonexistent(self) -> None:
        """Get nonexistent key returns None."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        assert await cache.get("nonexistent") is None

    async def test_delete(self) -> None:
        """Delete removes key."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        await cache.set("key1", "value1")
        await cache.delete("key1")
        assert await cache.get("key1") is None

    async def test_exists(self) -> None:
        """exists() checks key presence."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        assert not await cache.exists("key1")
        await cache.set("key1", "value1")
        assert await cache.exists("key1")
        await cache.delete("key1")
        assert not await cache.exists("key1")

    async def test_flush(self) -> None:
        """flush() clears all keys."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.flush()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert len(cache._cache) == 0

    async def test_ttl_expiry(self) -> None:
        """Keys with TTL expire after timeout."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        await cache.set("key1", "value1", ttl=1)  # 1 second TTL
        assert await cache.get("key1") == "value1"

        await asyncio.sleep(1.1)  # Wait for expiry
        assert await cache.get("key1") is None
        assert not await cache.exists("key1")

    async def test_no_ttl_persists(self) -> None:
        """Keys without TTL persist."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        await cache.set("key1", "value1")  # No TTL
        await asyncio.sleep(0.1)
        assert await cache.get("key1") == "value1"

    async def test_lru_eviction(self) -> None:
        """Oldest key is evicted when max_size exceeded."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config, max_size=3)
        await cache.connect()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        # Cache full: [key1, key2, key3]

        await cache.set("key4", "value4")
        # key1 evicted: [key2, key3, key4]

        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    async def test_lru_access_updates_order(self) -> None:
        """Accessing a key moves it to the end (most recent)."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config, max_size=3)
        await cache.connect()

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.set("key3", "value3")
        # Order: [key1, key2, key3]

        await cache.get("key1")  # Access key1, moves to end
        # Order: [key2, key3, key1]

        await cache.set("key4", "value4")
        # key2 evicted: [key3, key1, key4]

        assert await cache.get("key1") == "value1"  # Still present
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"
        assert await cache.get("key4") == "value4"

    async def test_update_existing_key(self) -> None:
        """Setting existing key updates value."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        cache = MemoryCache(config)
        await cache.connect()

        await cache.set("key1", "value1")
        await cache.set("key1", "value2")
        assert await cache.get("key1") == "value2"
