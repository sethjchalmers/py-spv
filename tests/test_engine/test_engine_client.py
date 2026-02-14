"""Tests for SPVWalletEngine lifecycle and service registry."""

from __future__ import annotations

import pytest

from spv_wallet.config.settings import (
    AppConfig,
    CacheConfig,
    DatabaseConfig,
    DatabaseEngine,
)
from spv_wallet.engine.client import SPVWalletEngine


class TestSPVWalletEngine:
    """Test engine initialization, lifecycle, and health checks."""

    async def test_init(self) -> None:  # noqa: ASYNC910
        """Engine can be instantiated with config."""
        config = AppConfig()
        engine = SPVWalletEngine(config)
        assert not engine.is_initialized
        assert engine.config == config

    async def test_initialize_and_close(self) -> None:
        """Engine can be initialized and closed."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)

        await engine.initialize()
        assert engine.is_initialized
        assert engine.datastore.is_open
        assert engine.cache.is_connected

        await engine.close()
        assert not engine.is_initialized

    async def test_double_initialize_raises(self) -> None:
        """Cannot initialize twice."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)

        await engine.initialize()
        with pytest.raises(RuntimeError, match="already initialized"):
            await engine.initialize()
        await engine.close()

    async def test_close_idempotent(self) -> None:
        """close() can be called multiple times."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)

        await engine.initialize()
        await engine.close()
        await engine.close()  # Should not raise

    async def test_datastore_property_before_init(self) -> None:  # noqa: ASYNC910
        """Accessing datastore before init raises RuntimeError."""
        config = AppConfig()
        engine = SPVWalletEngine(config)

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = engine.datastore

    async def test_cache_property_before_init(self) -> None:  # noqa: ASYNC910
        """Accessing cache before init raises RuntimeError."""
        config = AppConfig()
        engine = SPVWalletEngine(config)

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = engine.cache

    async def test_health_check_not_initialized(self) -> None:
        """Health check before init shows not_initialized."""
        config = AppConfig()
        engine = SPVWalletEngine(config)

        status = await engine.health_check()
        assert status["engine"] == "not_initialized"

    async def test_transaction_service_before_init(self) -> None:  # noqa: ASYNC910
        """Accessing transaction_service before init raises RuntimeError."""
        config = AppConfig()
        engine = SPVWalletEngine(config)

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = engine.transaction_service

    async def test_transaction_service_after_init(self) -> None:
        """transaction_service is available after init."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()
        assert engine.transaction_service is not None
        await engine.close()

    async def test_chain_service_before_init(self) -> None:  # noqa: ASYNC910
        """chain_service is None before init."""
        config = AppConfig()
        engine = SPVWalletEngine(config)
        assert engine.chain_service is None

    async def test_chain_service_after_init(self) -> None:
        """chain_service may or may not be available after init."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()
        # chain_service can be a ChainService or None depending on
        # whether ARC/BHS connect successfully in the test environment
        await engine.close()

    async def test_health_check_includes_chain(self) -> None:
        """Health check includes chain status."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()
        status = await engine.health_check()
        assert "chain" in status
        await engine.close()
    async def test_health_check_initialized(self) -> None:
        """Health check after init shows all ok."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)

        await engine.initialize()
        status = await engine.health_check()
        assert status["engine"] == "ok"
        assert status["datastore"] == "ok"
        assert status["cache"] == "ok"

        await engine.close()

    async def test_health_check_after_close(self) -> None:
        """Health check after close shows not_initialized."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)

        await engine.initialize()
        await engine.close()

        status = await engine.health_check()
        assert status["engine"] == "not_initialized"
