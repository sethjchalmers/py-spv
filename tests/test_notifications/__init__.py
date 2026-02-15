"""Tests for notification service and events."""

from __future__ import annotations

import asyncio

import pytest

from spv_wallet.notifications.events import RawEvent, TransactionEvent
from spv_wallet.notifications.service import NotificationService


class TestRawEvent:
    """Tests for RawEvent."""

    def test_create(self) -> None:
        e = RawEvent(type="test", content={"key": "value"})
        assert e.type == "test"
        assert e.content == {"key": "value"}

    def test_frozen(self) -> None:
        e = RawEvent(type="test")
        with pytest.raises(AttributeError):
            e.type = "other"  # type: ignore[misc]

    def test_to_dict(self) -> None:
        e = RawEvent(type="test", content={"k": 1})
        d = e.to_dict()
        assert d["type"] == "test"
        assert d["content"] == {"k": 1}

    def test_default_content(self) -> None:
        e = RawEvent(type="test")
        assert e.content == {}


class TestTransactionEvent:
    """Tests for TransactionEvent."""

    def test_create(self) -> None:
        e = TransactionEvent(
            transaction_id="abc123",
            xpub_id="xpub...",
            status="mined",
            value=1000,
        )
        assert e.type == "transaction"
        assert e.transaction_id == "abc123"
        assert e.value == 1000

    def test_to_dict(self) -> None:
        e = TransactionEvent(transaction_id="tx1", status="broadcasted")
        d = e.to_dict()
        assert d["type"] == "transaction"
        assert d["transaction_id"] == "tx1"
        assert d["status"] == "broadcasted"

    def test_inherits_raw_event(self) -> None:
        e = TransactionEvent(transaction_id="tx1")
        assert isinstance(e, RawEvent)


class TestNotificationService:
    """Tests for NotificationService."""

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        svc = NotificationService()
        assert not svc.is_running
        await svc.start()
        assert svc.is_running
        await svc.stop()
        assert not svc.is_running

    @pytest.mark.asyncio
    async def test_idempotent_start(self) -> None:
        svc = NotificationService()
        await svc.start()
        await svc.start()
        assert svc.is_running
        await svc.stop()

    @pytest.mark.asyncio
    async def test_fan_out(self) -> None:
        svc = NotificationService()
        q1 = svc.add_subscriber("sub1")
        q2 = svc.add_subscriber("sub2")
        await svc.start()

        event = RawEvent(type="test", content={"v": 1})
        await svc.notify(event)

        # Wait a bit for the exchange loop
        await asyncio.sleep(0.1)

        e1 = q1.get_nowait()
        e2 = q2.get_nowait()
        assert e1.type == "test"
        assert e2.type == "test"
        await svc.stop()

    @pytest.mark.asyncio
    async def test_remove_subscriber(self) -> None:
        svc = NotificationService()
        q = svc.add_subscriber("sub1")
        svc.remove_subscriber("sub1")
        await svc.start()

        await svc.notify(RawEvent(type="test"))
        await asyncio.sleep(0.1)

        assert q.empty()  # Removed subscriber should not receive
        await svc.stop()

    @pytest.mark.asyncio
    async def test_idempotent_stop(self) -> None:
        svc = NotificationService()
        await svc.stop()  # Should not raise
        assert not svc.is_running
