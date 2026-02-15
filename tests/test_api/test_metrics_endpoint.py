"""Tests for the metrics endpoint and middleware integration in the app."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from spv_wallet.api.app import create_app
from spv_wallet.config.settings import AppConfig


@pytest.fixture
def _mock_engine() -> MagicMock:
    engine = MagicMock()
    engine.initialize = AsyncMock()
    engine.close = AsyncMock()
    engine.is_initialized = True
    return engine


class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""

    def test_metrics_endpoint_returns_prometheus_format(self) -> None:
        cfg = AppConfig()
        app = create_app(config=cfg)

        with (
            patch("spv_wallet.api.app.SPVWalletEngine") as mock_cls,
        ):
            engine = MagicMock()
            engine.initialize = AsyncMock()
            engine.close = AsyncMock()
            mock_cls.return_value = engine

            client = TestClient(app)
            resp = client.get("/metrics")
            assert resp.status_code == 200
            # Prometheus text format
            assert "text/plain" in resp.headers.get("content-type", "")

    def test_health_still_works(self) -> None:
        cfg = AppConfig()
        app = create_app(config=cfg)

        with patch("spv_wallet.api.app.SPVWalletEngine") as mock_cls:
            engine = MagicMock()
            engine.initialize = AsyncMock()
            engine.close = AsyncMock()
            mock_cls.return_value = engine

            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            assert resp.json() == {"status": "ok"}
