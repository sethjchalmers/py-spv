"""Tests for webhook notifier and manager."""

from __future__ import annotations

import time

import pytest

from spv_wallet.notifications.events import RawEvent
from spv_wallet.notifications.webhook import (
    WebhookConfig,
    WebhookManager,
    WebhookNotifier,
)


class TestWebhookConfig:
    """Tests for WebhookConfig."""

    def test_defaults(self) -> None:
        cfg = WebhookConfig(url="https://example.com/hook")
        assert cfg.url == "https://example.com/hook"
        assert cfg.token_header == "Authorization"
        assert cfg.token_value == ""
        assert cfg.banned_until == 0.0


class TestWebhookNotifier:
    """Tests for WebhookNotifier."""

    def test_url_property(self) -> None:
        cfg = WebhookConfig(url="https://example.com/hook")
        n = WebhookNotifier(cfg)
        assert n.url == "https://example.com/hook"

    def test_not_banned_by_default(self) -> None:
        cfg = WebhookConfig(url="https://example.com/hook")
        n = WebhookNotifier(cfg)
        assert not n.is_banned

    def test_banned(self) -> None:
        cfg = WebhookConfig(url="https://example.com/hook", banned_until=time.time() + 3600)
        n = WebhookNotifier(cfg)
        assert n.is_banned

    def test_enqueue_drops_when_banned(self) -> None:
        cfg = WebhookConfig(url="https://example.com/hook", banned_until=time.time() + 3600)
        n = WebhookNotifier(cfg)
        event = RawEvent(type="test")
        # Should not raise — silently drops
        n.enqueue(event)


class TestWebhookManager:
    """Tests for WebhookManager."""

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        mgr = WebhookManager()
        assert not mgr.is_running
        await mgr.start()
        assert mgr.is_running
        await mgr.stop()
        assert not mgr.is_running

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self) -> None:
        mgr = WebhookManager()
        await mgr.start()
        await mgr.subscribe("https://example.com/a")
        await mgr.subscribe("https://example.com/b")
        assert len(mgr.get_all()) == 2

        await mgr.unsubscribe("https://example.com/a")
        assert len(mgr.get_all()) == 1

        await mgr.stop()

    @pytest.mark.asyncio
    async def test_get_all_format(self) -> None:
        mgr = WebhookManager()
        await mgr.start()
        await mgr.subscribe("https://example.com/hook")
        hooks = mgr.get_all()
        assert len(hooks) == 1
        assert hooks[0]["url"] == "https://example.com/hook"
        assert hooks[0]["banned"] == "False"
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_dispatch(self) -> None:
        mgr = WebhookManager()
        await mgr.start()
        # Dispatch without subscribers should not raise
        event = RawEvent(type="test")
        mgr.dispatch(event)
        await mgr.stop()

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent(self) -> None:
        mgr = WebhookManager()
        await mgr.start()
        # Should not raise
        await mgr.unsubscribe("https://nonexistent.com/hook")
        await mgr.stop()
