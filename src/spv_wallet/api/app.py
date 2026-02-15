"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest
from starlette.responses import Response

from spv_wallet import __version__
from spv_wallet.api.middleware.cors import setup_cors
from spv_wallet.api.v1 import v1_router
from spv_wallet.api.v2 import v2_router
from spv_wallet.config.settings import AppConfig
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.errors.spv_errors import SPVError
from spv_wallet.metrics.collector import EngineMetrics
from spv_wallet.metrics.middleware import PrometheusMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle hooks.

    Initialises the engine (datastore, cache, services) on startup and
    gracefully shuts down on exit.
    """
    config: AppConfig = app.state.config
    engine = SPVWalletEngine(config)

    # Engine metrics
    metrics = EngineMetrics()
    app.state.metrics = metrics

    try:
        await engine.initialize()
        app.state.engine = engine
        logger.info("SPV Wallet engine initialized")
        yield
    finally:
        await engine.close()
        logger.info("SPV Wallet engine shut down")


def create_app(*, config: AppConfig | None = None) -> FastAPI:
    """Build and return the FastAPI application.

    Args:
        config: Optional AppConfig. If *None*, a default config is created
            from environment variables.
    """
    if config is None:
        config = AppConfig()

    app = FastAPI(
        title="py-spv",
        version=__version__,
        description="Python SPV Wallet for BSV Blockchain",
        lifespan=_lifespan,
    )

    # Store config on app.state for lifespan access
    app.state.config = config

    # -- Middleware --
    setup_cors(app)

    # -- Error handler --
    @app.exception_handler(SPVError)
    async def _spv_error_handler(request: Request, exc: SPVError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    # -- Base routes --
    @app.get("/health", tags=["base"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics", tags=["base"], include_in_schema=False)
    async def metrics_endpoint() -> Response:
        """Prometheus metrics endpoint."""
        registry = app.state.metrics.registry if hasattr(app.state, "metrics") else None
        body = generate_latest(registry) if registry else generate_latest()
        return Response(
            content=body,
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    # -- Prometheus request metrics middleware --
    if hasattr(app.state, "metrics"):
        app.add_middleware(PrometheusMiddleware, registry=app.state.metrics.registry)

    # -- Mount v1 API --
    app.include_router(v1_router)

    # -- Mount v2 API --
    app.include_router(v2_router)

    return app
