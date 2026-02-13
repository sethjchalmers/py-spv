"""SPVWalletEngine — central engine client owning all services."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spv_wallet.config.settings import AppConfig


class SPVWalletEngine:
    """Central engine that owns all services and infrastructure.

    Mirrors the Go ``engine.Client`` with a functional-options-style configuration.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        # Service references populated during initialise()
        # self._datastore = ...
        # self._cache = ...
        # self._chain = ...
        # self._task_manager = ...

    async def initialise(self) -> None:
        """Initialise datastore, run migrations, and start services."""

    async def close(self) -> None:
        """Gracefully shut down all services and connections."""
