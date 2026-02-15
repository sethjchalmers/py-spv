"""Tests for new Phase 7 config additions (ClusterConfig, NotificationConfig)."""

from __future__ import annotations

from spv_wallet.config.settings import AppConfig, ClusterConfig, NotificationConfig


class TestClusterConfig:
    """Tests for ClusterConfig."""

    def test_defaults(self) -> None:
        cfg = ClusterConfig()
        assert cfg.coordinator == "memory"
        assert cfg.redis_url == "redis://localhost:6379/2"
        assert cfg.prefix == "bsv_"


class TestNotificationConfig:
    """Tests for NotificationConfig."""

    def test_defaults(self) -> None:
        cfg = NotificationConfig()
        assert cfg.enabled is True
        assert cfg.webhook_max_retries == 2
        assert cfg.webhook_ban_time == 3600


class TestAppConfigPhase7:
    """Tests for Phase 7 additions to AppConfig."""

    def test_cluster_field(self) -> None:
        cfg = AppConfig()
        assert cfg.cluster.coordinator == "memory"

    def test_notifications_field(self) -> None:
        cfg = AppConfig()
        assert cfg.notifications.enabled is True
