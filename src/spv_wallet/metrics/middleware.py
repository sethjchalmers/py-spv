"""Prometheus HTTP request metrics middleware for FastAPI.

Tracks:
- ``http_request_total`` (counter) — total requests by method, path, status
- ``http_request_duration_seconds`` (histogram) — request duration by method, path
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Callable

    from prometheus_client import CollectorRegistry
    from starlette.requests import Request
    from starlette.responses import Response

_APP_LABEL = "spv-wallet"

_LABELS = ("method", "path", "status_code", "app")
_DURATION_LABELS = ("method", "path", "app")


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that records request count and duration."""

    def __init__(self, app: object, *, registry: CollectorRegistry) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._request_count = Counter(
            "http_request_total",
            "Total HTTP requests",
            _LABELS,
            registry=registry,
        )
        self._request_duration = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            _DURATION_LABELS,
            registry=registry,
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[type-arg]
        """Wrap each request with timing and counting."""
        method = request.method
        path = request.url.path
        start = time.monotonic()

        response: Response = await call_next(request)

        duration = time.monotonic() - start
        status = str(response.status_code)

        self._request_count.labels(
            method=method,
            path=path,
            status_code=status,
            app=_APP_LABEL,
        ).inc()
        self._request_duration.labels(
            method=method,
            path=path,
            app=_APP_LABEL,
        ).observe(duration)

        return response
