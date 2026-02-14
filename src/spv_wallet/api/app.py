"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from spv_wallet import __version__

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown lifecycle hooks."""
    # TODO: initialise engine, datastore, cache, chain service
    yield
    # TODO: graceful shutdown


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="py-spv",
        version=__version__,
        description="Python SPV Wallet for BSV Blockchain",
        lifespan=_lifespan,
    )

    # TODO: register middleware (CORS, auth, metrics)
    # TODO: mount v1, v2, and paymail routers

    @app.get("/health", tags=["base"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
