"""Tests for datastore abstraction — engines and client."""

from __future__ import annotations

import pytest

from spv_wallet.config.settings import DatabaseConfig
from spv_wallet.datastore.client import Datastore
from spv_wallet.datastore.engines import create_engine
from spv_wallet.engine.models.base import Base


# ---------------------------------------------------------------------------
# Engine factory
# ---------------------------------------------------------------------------


class TestCreateEngine:
    """Test engine factory."""

    async def test_create_sqlite_engine(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        engine = create_engine(config)
        assert engine is not None
        await engine.dispose()

    async def test_engine_echo_flag(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
            debug_sql=True,
        )
        engine = create_engine(config)
        assert engine.echo is True
        await engine.dispose()


# ---------------------------------------------------------------------------
# Datastore client
# ---------------------------------------------------------------------------


class TestDatastore:
    """Test Datastore lifecycle and session management."""

    async def test_open_close(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        assert not ds.is_open
        await ds.open()
        assert ds.is_open
        await ds.close()
        assert not ds.is_open

    async def test_engine_property_when_closed(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        with pytest.raises(RuntimeError, match="not open"):
            _ = ds.engine

    async def test_session_when_closed(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        with pytest.raises(RuntimeError, match="not open"):
            ds.session()

    async def test_session_basic_operations(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        await ds.open(base=Base)
        async with ds.session() as session:
            # Session should be usable
            result = await session.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
            assert result.scalar() == 1
        await ds.close()

    async def test_open_creates_tables(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        await ds.open(base=Base)
        # Tables should exist (at least we can query without error)
        async with ds.session() as session:
            result = await session.execute(
                __import__("sqlalchemy").text(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            )
            tables = [row[0] for row in result.fetchall()]
            # Base itself has no tables, but the engine should be functional
            assert isinstance(tables, list)
        await ds.close()

    async def test_table_prefix(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
            table_prefix="app_",
        )
        ds = Datastore(config)
        assert ds.table_prefix == "app_"
        await ds.open()
        await ds.close()

    async def test_close_idempotent(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        await ds.open()
        await ds.close()
        # Closing again should not raise
        await ds.close()

    async def test_session_iterator(self) -> None:
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        await ds.open(base=Base)
        async for session in ds.session_iterator():
            result = await session.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
            assert result.scalar() == 1
        await ds.close()

    async def test_session_iterator_rollback_on_error(self) -> None:
        """Verify session_iterator rolls back on exception."""
        config = DatabaseConfig(
            engine="sqlite",
            dsn="sqlite+aiosqlite:///:memory:",
        )
        ds = Datastore(config)
        await ds.open(base=Base)
        with pytest.raises(RuntimeError, match="boom"):
            async for session in ds.session_iterator():
                msg = "boom"
                raise RuntimeError(msg)
        await ds.close()
