"""Tests for cluster module — pubsub and client."""

from __future__ import annotations

import pytest

from spv_wallet.cluster.client import ClusterClient, Coordinator
from spv_wallet.cluster.pubsub import Channel, MemoryPubSub


class TestChannel:
    """Tests for Channel enum."""

    def test_destination_new(self) -> None:
        assert Channel.DESTINATION_NEW == "new-destination"

    def test_is_str(self) -> None:
        assert isinstance(Channel.DESTINATION_NEW, str)


class TestMemoryPubSub:
    """Tests for in-memory pub/sub."""

    @pytest.mark.asyncio
    async def test_publish_subscribe(self) -> None:
        ps = MemoryPubSub()
        received: list[str] = []

        async def callback(msg: str) -> None:
            received.append(msg)

        await ps.subscribe("chan1", callback)
        await ps.publish("chan1", "hello")
        assert received == ["hello"]

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        ps = MemoryPubSub()
        r1: list[str] = []
        r2: list[str] = []

        async def cb1(msg: str) -> None:
            r1.append(msg)

        async def cb2(msg: str) -> None:
            r2.append(msg)

        await ps.subscribe("chan1", cb1)
        await ps.subscribe("chan1", cb2)
        await ps.publish("chan1", "msg")
        assert r1 == ["msg"]
        assert r2 == ["msg"]

    @pytest.mark.asyncio
    async def test_no_crosstalk(self) -> None:
        ps = MemoryPubSub()
        received: list[str] = []

        async def callback(msg: str) -> None:
            received.append(msg)

        await ps.subscribe("chan1", callback)
        await ps.publish("chan2", "hello")  # Different channel
        assert received == []

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        ps = MemoryPubSub()
        received: list[str] = []

        async def callback(msg: str) -> None:
            received.append(msg)

        await ps.subscribe("chan1", callback)
        await ps.close()
        await ps.publish("chan1", "hello")
        assert received == []  # Cleared after close

    @pytest.mark.asyncio
    async def test_error_in_callback_does_not_crash(self) -> None:
        ps = MemoryPubSub()

        async def bad_callback(msg: str) -> None:
            raise ValueError("boom")

        await ps.subscribe("chan1", bad_callback)
        # Should not raise
        await ps.publish("chan1", "hello")


class TestCoordinator:
    """Tests for Coordinator enum."""

    def test_memory(self) -> None:
        assert Coordinator.MEMORY == "memory"

    def test_redis(self) -> None:
        assert Coordinator.REDIS == "redis"


class TestClusterClient:
    """Tests for ClusterClient."""

    @pytest.mark.asyncio
    async def test_memory_connect(self) -> None:
        client = ClusterClient(coordinator=Coordinator.MEMORY)
        await client.connect()
        assert client.pubsub is not None
        await client.close()

    @pytest.mark.asyncio
    async def test_not_connected_raises(self) -> None:
        client = ClusterClient()
        with pytest.raises(RuntimeError, match="not connected"):
            _ = client.pubsub

    @pytest.mark.asyncio
    async def test_memory_try_lock(self) -> None:
        client = ClusterClient(coordinator=Coordinator.MEMORY)
        await client.connect()
        # Memory coordinator always returns True
        assert await client.try_lock("test-key") is True
        await client.close()

    @pytest.mark.asyncio
    async def test_idempotent_connect(self) -> None:
        client = ClusterClient(coordinator=Coordinator.MEMORY)
        await client.connect()
        await client.connect()  # Should not raise
        await client.close()

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        client = ClusterClient(coordinator=Coordinator.MEMORY)
        await client.close()  # Should not raise when not connected

    @pytest.mark.asyncio
    async def test_pubsub_works(self) -> None:
        client = ClusterClient(coordinator=Coordinator.MEMORY)
        await client.connect()
        received: list[str] = []

        async def cb(msg: str) -> None:
            received.append(msg)

        await client.pubsub.subscribe("test", cb)
        await client.pubsub.publish("test", "msg1")
        assert received == ["msg1"]
        await client.close()

    @pytest.mark.asyncio
    async def test_coordinator_from_string(self) -> None:
        client = ClusterClient(coordinator="memory")
        await client.connect()
        assert client.pubsub is not None
        await client.close()
