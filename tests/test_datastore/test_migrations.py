"""Tests for auto-migration support — datastore/migrations.py."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from spv_wallet.datastore.migrations import drop_all_tables, run_auto_migrate


class TestAutoMigrate:
    """Test programmatic table creation and teardown."""

    async def test_auto_migrate_creates_all_tables(self) -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        await run_auto_migrate(engine)

        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            tables = {row[0] for row in result.fetchall()}

        expected = {
            "xpubs",
            "access_keys",
            "destinations",
            "draft_transactions",
            "transactions",
            "utxos",
            "paymail_addresses",
            "contacts",
            "webhooks",
        }
        assert expected.issubset(tables)
        await engine.dispose()

    async def test_auto_migrate_idempotent(self) -> None:
        """Running auto-migrate twice should not raise."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        await run_auto_migrate(engine)
        await run_auto_migrate(engine)  # Should not raise
        await engine.dispose()

    async def test_drop_all_tables(self) -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        await run_auto_migrate(engine)

        # Verify tables exist
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT count(*) FROM sqlite_master WHERE type='table'")
            )
            count_before = result.scalar()
        assert count_before is not None and count_before > 0

        # Drop all
        await drop_all_tables(engine)

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT count(*) FROM sqlite_master "
                    "WHERE type='table' AND name != 'sqlite_sequence'"
                )
            )
            count_after = result.scalar()
        assert count_after == 0
        await engine.dispose()

    async def test_migrate_then_insert(self) -> None:
        """Verify tables are functional after migration."""
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        from spv_wallet.engine.models.xpub import Xpub

        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        await run_auto_migrate(engine)

        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            xpub = Xpub(id="a" * 64, current_balance=42)
            session.add(xpub)
            await session.commit()
            result = await session.get(Xpub, "a" * 64)
            assert result is not None
            assert result.current_balance == 42

        await engine.dispose()
