"""SPVWalletEngine — central engine client owning all services."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spv_wallet.cache.client import CacheClient
    from spv_wallet.chain.service import ChainService
    from spv_wallet.config.settings import AppConfig
    from spv_wallet.datastore.client import Datastore
    from spv_wallet.engine.services.access_key_service import AccessKeyService
    from spv_wallet.engine.services.destination_service import DestinationService
    from spv_wallet.engine.services.transaction_service import TransactionService
    from spv_wallet.engine.services.utxo_service import UTXOService
    from spv_wallet.engine.services.xpub_service import XPubService

# Error messages
_ERR_NOT_INITIALIZED = "Engine not initialized. Call initialize() first."


class SPVWalletEngine:
    """Central engine that owns all services and infrastructure.

    Mirrors the Go ``engine.Client`` with a functional-options-style configuration.
    Provides lifecycle management and service registry pattern.
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize engine with configuration.

        Args:
            config: Application configuration with datastore, cache, chain settings.
        """
        self._config = config
        self._initialized = False

        # Infrastructure components
        self._datastore: Datastore | None = None
        self._cache: CacheClient | None = None
        self._chain: ChainService | None = None

        # Services
        self._xpub_service: XPubService | None = None
        self._destination_service: DestinationService | None = None
        self._utxo_service: UTXOService | None = None
        self._access_key_service: AccessKeyService | None = None
        self._transaction_service: TransactionService | None = None

    async def initialize(self) -> None:
        """Initialize datastore, run migrations, and start services.

        Raises:
            RuntimeError: If already initialized.
        """
        if self._initialized:
            msg = "Engine already initialized"
            raise RuntimeError(msg)

        # Import here to avoid circular deps
        from spv_wallet.cache.client import CacheClient
        from spv_wallet.datastore.client import Datastore
        from spv_wallet.datastore.migrations import run_auto_migrate
        from spv_wallet.engine.models.base import Base

        # Initialize datastore
        self._datastore = Datastore(self._config.db)
        await self._datastore.open(base=Base)

        # Run migrations
        await run_auto_migrate(self._datastore.engine)

        # Initialize cache
        self._cache = CacheClient(self._config.cache)
        await self._cache.connect()

        # Initialize services
        from spv_wallet.engine.services.access_key_service import AccessKeyService
        from spv_wallet.engine.services.destination_service import DestinationService
        from spv_wallet.engine.services.transaction_service import TransactionService
        from spv_wallet.engine.services.utxo_service import UTXOService
        from spv_wallet.engine.services.xpub_service import XPubService

        self._xpub_service = XPubService(self)
        self._destination_service = DestinationService(self)
        self._utxo_service = UTXOService(self)
        self._access_key_service = AccessKeyService(self)
        self._transaction_service = TransactionService(self)

        # Initialize chain service (ARC + BHS)
        from spv_wallet.chain.service import ChainService

        self._chain = ChainService(self._config)
        try:
            await self._chain.connect()
        except Exception:
            # Chain service is optional — engine works without it
            self._chain = None

        # TODO Phase 7: Initialize task manager

        self._initialized = True

    async def close(self) -> None:
        """Gracefully shut down all services and connections.

        Can be called multiple times (idempotent).
        """
        if not self._initialized:
            return

        # Tear down services
        self._transaction_service = None
        self._xpub_service = None
        self._destination_service = None
        self._utxo_service = None
        self._access_key_service = None

        # Close chain service
        if self._chain is not None:
            await self._chain.close()
            self._chain = None

        # Close cache
        if self._cache is not None:
            await self._cache.close()
            self._cache = None

        # Close datastore
        if self._datastore is not None:
            await self._datastore.close()
            self._datastore = None

        # TODO Phase 7: Close task manager

        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the engine is initialized."""
        return self._initialized

    @property
    def datastore(self) -> Datastore:
        """Get the datastore instance.

        Returns:
            The configured datastore.

        Raises:
            RuntimeError: If engine not initialized.
        """
        if self._datastore is None:
            raise RuntimeError(_ERR_NOT_INITIALIZED)
        return self._datastore

    @property
    def cache(self) -> CacheClient:
        """Get the cache client instance.

        Returns:
            The configured cache client.

        Raises:
            RuntimeError: If engine not initialized.
        """
        if self._cache is None:
            raise RuntimeError(_ERR_NOT_INITIALIZED)
        return self._cache

    @property
    def config(self) -> AppConfig:
        """Get the application configuration."""
        return self._config

    @property
    def xpub_service(self) -> XPubService:
        """Get the xPub service."""
        if self._xpub_service is None:
            raise RuntimeError(_ERR_NOT_INITIALIZED)
        return self._xpub_service

    @property
    def destination_service(self) -> DestinationService:
        """Get the destination service."""
        if self._destination_service is None:
            raise RuntimeError(_ERR_NOT_INITIALIZED)
        return self._destination_service

    @property
    def utxo_service(self) -> UTXOService:
        """Get the UTXO service."""
        if self._utxo_service is None:
            raise RuntimeError(_ERR_NOT_INITIALIZED)
        return self._utxo_service

    @property
    def access_key_service(self) -> AccessKeyService:
        """Get the access key service."""
        if self._access_key_service is None:
            raise RuntimeError(_ERR_NOT_INITIALIZED)
        return self._access_key_service

    @property
    def transaction_service(self) -> TransactionService:
        """Get the transaction service."""
        if self._transaction_service is None:
            raise RuntimeError(_ERR_NOT_INITIALIZED)
        return self._transaction_service

    @property
    def chain_service(self) -> ChainService | None:
        """Get the chain service (ARC + BHS).

        Returns None if chain service is not available (optional dependency).
        """
        return self._chain

    async def health_check(self) -> dict[str, str]:
        """Check health status of all engine components.

        Returns:
            Dictionary with component statuses ('ok', 'error', 'not_initialized').
        """
        status = {
            "engine": "ok" if self._initialized else "not_initialized",
            "datastore": "unknown",
            "cache": "unknown",
            "chain": "unknown",
        }

        if self._initialized:
            # Check datastore
            if self._datastore and self._datastore.is_open:
                status["datastore"] = "ok"
            else:
                status["datastore"] = "error"

            # Check cache
            if self._cache and self._cache.is_connected:
                status["cache"] = "ok"
            else:
                status["cache"] = "error"

            # Check chain
            if self._chain and self._chain.is_connected:
                status["chain"] = "ok"
            else:
                status["chain"] = "not_connected"

        return status
