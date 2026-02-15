"""Prometheus metrics middleware — re-exports from metrics package."""

from __future__ import annotations

from spv_wallet.metrics.middleware import PrometheusMiddleware

__all__ = ["PrometheusMiddleware"]
