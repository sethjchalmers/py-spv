"""Tests for datastore/engines.py — including PostgreSQL config path."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from spv_wallet.config.settings import DatabaseConfig
from spv_wallet.datastore.engines import create_engine


class TestCreateEngine:
    async def test_sqlite_engine_no_pool_settings(self) -> None:
        """SQLite engines should not set pool_size / max_overflow."""
        config = DatabaseConfig(dsn="sqlite+aiosqlite:///:memory:")
        engine = create_engine(config)
        assert engine is not None
        # SQLite uses NullPool by default with create_async_engine
        await engine.dispose()

    def test_postgresql_engine_has_pool_settings(self) -> None:
        """PostgreSQL DSNs should configure pool_size and max_overflow."""
        config = DatabaseConfig(
            dsn="postgresql+asyncpg://user:pass@localhost/testdb",
            max_idle_connections=5,
            max_open_connections=20,
            debug_sql=True,
        )
        with patch(
            "spv_wallet.datastore.engines.create_async_engine",
            return_value=MagicMock(),
        ) as mock_create:
            _ = create_engine(config)
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["pool_size"] == 5
            assert call_kwargs["max_overflow"] == 15  # 20 - 5
            assert call_kwargs["pool_pre_ping"] is True
            assert call_kwargs["echo"] is True
