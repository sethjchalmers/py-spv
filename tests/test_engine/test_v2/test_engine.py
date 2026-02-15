"""Tests for V2Engine lifecycle and service wiring."""

from __future__ import annotations

import pytest

from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine
from spv_wallet.engine.client import SPVWalletEngine


@pytest.fixture
async def engine():
    """Create an initialized engine with in-memory SQLite."""
    config = AppConfig(
        db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    yield eng
    await eng.close()


class TestV2EngineLifecycle:
    """V2Engine is created, initialized, and torn down with the main engine."""

    async def test_v2_available_after_init(self, engine: SPVWalletEngine) -> None:
        v2 = engine.v2
        assert v2 is not None

    async def test_v2_services_available(self, engine: SPVWalletEngine) -> None:
        v2 = engine.v2
        assert v2.users is not None
        assert v2.paymails is not None
        assert v2.contacts is not None
        assert v2.outlines is not None
        assert v2.record is not None
        assert v2.tx_sync is not None

    def test_v2_not_initialized_raises(self) -> None:
        from unittest.mock import MagicMock

        from spv_wallet.engine.v2.engine import V2Engine

        v2 = V2Engine(MagicMock())
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = v2.users

    def test_v2_close_clears_services(self) -> None:
        from unittest.mock import MagicMock

        from spv_wallet.engine.v2.engine import V2Engine

        v2 = V2Engine(MagicMock())
        v2.initialize()
        assert v2.users is not None
        v2.close()
        with pytest.raises(RuntimeError):
            _ = v2.users
