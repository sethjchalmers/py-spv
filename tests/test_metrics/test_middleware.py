"""Tests for the Prometheus request middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry

from spv_wallet.metrics.middleware import PrometheusMiddleware


@pytest.fixture
def _app_with_metrics() -> tuple[FastAPI, CollectorRegistry]:
    registry = CollectorRegistry()
    app = FastAPI()
    app.add_middleware(PrometheusMiddleware, registry=registry)

    @app.get("/test")
    async def test_endpoint() -> dict[str, str]:
        return {"ok": "yes"}

    return app, registry


class TestPrometheusMiddleware:
    """Tests for PrometheusMiddleware."""

    def test_increments_request_count(self, _app_with_metrics: tuple) -> None:
        app, registry = _app_with_metrics
        client = TestClient(app)
        client.get("/test")
        # Check that request count metric was created
        # (prometheus_client internal API for testing)
        metrics = list(registry.collect())
        metric_names = [m.name for m in metrics]
        assert "http_request" in metric_names

    def test_records_duration(self, _app_with_metrics: tuple) -> None:
        app, registry = _app_with_metrics
        client = TestClient(app)
        client.get("/test")
        metrics = list(registry.collect())
        metric_names = [m.name for m in metrics]
        assert "http_request_duration_seconds" in metric_names

    def test_multiple_requests(self, _app_with_metrics: tuple) -> None:
        app, registry = _app_with_metrics
        client = TestClient(app)
        client.get("/test")
        client.get("/test")
        client.get("/test")
        # Counter should have been incremented 3 times
        for metric in registry.collect():
            if metric.name == "http_request":
                for sample in metric.samples:
                    if sample.labels.get("path") == "/test":
                        assert sample.value == 3.0
                        return
        pytest.fail("Could not find http_request_total metric for /test")
