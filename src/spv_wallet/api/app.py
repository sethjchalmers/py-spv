"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from spv_wallet import __version__
from spv_wallet.api.middleware.cors import setup_cors
from spv_wallet.api.v1 import v1_router
from spv_wallet.config.settings import AppConfig
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.errors.spv_errors import SPVError

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

    # -- Mount v1 API --
    app.include_router(v1_router)

    return app
