"""Tests for CacheClient abstraction layer."""

from __future__ import annotations

import pytest

from spv_wallet.cache.client import CacheClient
from spv_wallet.cache.memory import MemoryCache
from spv_wallet.config.settings import CacheConfig, CacheEngine


class TestCacheClient:
    """Test cache client with in-memory backend."""

    async def test_init(self) -> None:  # noqa: ASYNC910
        """CacheClient can be instantiated."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)
        assert not client.is_connected

    async def test_connect_memory_backend(self) -> None:
        """Connect creates memory backend."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)

        await client.connect()
        assert client.is_connected
        assert isinstance(client._backend, MemoryCache)

        await client.close()

    async def test_close_idempotent(self) -> None:
        """close() can be called multiple times."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)

        await client.connect()
        await client.close()
        await client.close()  # Should not raise

    async def test_get_set_delete(self) -> None:
        """Basic CRUD operations."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)
        await client.connect()

        # Set and get
        await client.set("key1", "value1")
        assert await client.get("key1") == "value1"

        # Delete
        await client.delete("key1")
        assert await client.get("key1") is None

        await client.close()

    async def test_get_nonexistent(self) -> None:
        """Getting nonexistent key returns None."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)
        await client.connect()

        assert await client.get("nonexistent") is None

        await client.close()

    async def test_exists(self) -> None:
        """exists() checks key presence."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)
        await client.connect()

        assert not await client.exists("key1")
        await client.set("key1", "value1")
        assert await client.exists("key1")

        await client.close()

    async def test_flush(self) -> None:
        """flush() clears all keys."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)
        await client.connect()

        await client.set("key1", "value1")
        await client.set("key2", "value2")
        await client.flush()
        assert await client.get("key1") is None
        assert await client.get("key2") is None

        await client.close()

    async def test_operations_before_connect_raise(self) -> None:
        """Operations before connect raise RuntimeError."""
        config = CacheConfig(engine=CacheEngine.MEMORY)
        client = CacheClient(config)

        with pytest.raises(RuntimeError, match="not connected"):
            await client.get("key1")

        with pytest.raises(RuntimeError, match="not connected"):
            await client.set("key1", "value1")

        with pytest.raises(RuntimeError, match="not connected"):
            await client.delete("key1")

        with pytest.raises(RuntimeError, match="not connected"):
            await client.exists("key1")

        with pytest.raises(RuntimeError, match="not connected"):
            await client.flush()
