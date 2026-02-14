"""Tests for ModelOps mixin functionality."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.engine.models.xpub import Xpub


class TestModelOps:
    """Test ModelOps mixin with engine reference and lifecycle hooks."""

    async def test_model_without_engine(self) -> None:
        """Model can be created without engine reference."""
        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )
        assert xpub.engine is None

    async def test_model_with_engine(self) -> None:
        """Model can be created with engine reference."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
            engine=engine,
        )
        assert xpub.engine == engine

        await engine.close()

    async def test_engine_setter(self) -> None:
        """Engine can be set after model creation."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )
        xpub.engine = engine
        assert xpub.engine == engine

        await engine.close()

    async def test_is_new_transient(self) -> None:
        """Transient models report is_new=True."""
        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )
        assert xpub.is_new
        assert not xpub.not_new

    async def test_not_new_after_persist(self) -> None:
        """Persisted models report is_new=False."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )
        assert xpub.is_new

        # Persist via datastore
        async with engine.datastore.session() as session:
            session.add(xpub)
            await session.commit()

        assert xpub.not_new
        assert not xpub.is_new

        await engine.close()

    async def test_save_without_engine_raises(self) -> None:
        """save() without engine raises RuntimeError."""
        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )

        with pytest.raises(RuntimeError, match="engine not set"):
            await xpub.save()

    async def test_save_persists_model(self) -> None:
        """save() persists model to database."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
            engine=engine,
        )
        await xpub.save()

        # Verify persisted
        async with engine.datastore.session() as session:
            result = await session.execute(select(Xpub).where(Xpub.id == "test123"))
            loaded = result.scalar_one()
            assert loaded.id == "test123"
            assert loaded.current_balance == 1000

        await engine.close()

    async def test_save_updates_existing(self) -> None:
        """save() updates existing model."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
            engine=engine,
        )
        await xpub.save()

        # Update and save again
        xpub.current_balance = 2000
        await xpub.save()

        # Verify updated
        async with engine.datastore.session() as session:
            result = await session.execute(select(Xpub).where(Xpub.id == "test123"))
            loaded = result.scalar_one()
            assert loaded.current_balance == 2000

        await engine.close()

    async def test_get_metadata(self) -> None:
        """get_metadata returns value by key."""
        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )
        xpub.metadata_ = {"key1": "value1", "key2": 42}

        assert xpub.get_metadata("key1") == "value1"
        assert xpub.get_metadata("key2") == 42
        assert xpub.get_metadata("nonexistent") is None
        assert xpub.get_metadata("nonexistent", "default") == "default"

    async def test_set_metadata(self) -> None:
        """set_metadata sets value by key."""
        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )

        xpub.set_metadata("key1", "value1")
        assert xpub.metadata_["key1"] == "value1"

        xpub.set_metadata("key2", 42)
        assert xpub.metadata_["key2"] == 42

    async def test_update_metadata(self) -> None:
        """update_metadata updates multiple values."""
        xpub = Xpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
        )
        xpub.metadata_ = {"existing": "value"}

        xpub.update_metadata({"key1": "value1", "key2": 42})
        assert xpub.metadata_["existing"] == "value"
        assert xpub.metadata_["key1"] == "value1"
        assert xpub.metadata_["key2"] == 42


class TestLifecycleHooks:
    """Test before_save and after_save lifecycle hooks."""

    async def test_before_save_called(self) -> None:
        """before_save is called before persist."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        hook_called = []

        class TestXpub(Xpub):
            async def before_save(self) -> None:
                hook_called.append("before")

        xpub = TestXpub(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
            engine=engine,
        )
        await xpub.save()

        assert "before" in hook_called

        await engine.close()

    async def test_after_save_called(self) -> None:
        """after_save is called after persist."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        hook_called = []

        class TestXpubAfter(Xpub):
            async def after_save(self) -> None:
                hook_called.append("after")

        xpub = TestXpubAfter(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
            engine=engine,
        )
        await xpub.save()

        assert "after" in hook_called

        await engine.close()

    async def test_lifecycle_hook_order(self) -> None:
        """Lifecycle hooks are called in correct order."""
        config = AppConfig(
            db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
        )
        engine = SPVWalletEngine(config)
        await engine.initialize()

        call_order = []

        class TestXpubOrder(Xpub):
            async def before_save(self) -> None:
                call_order.append("before")

            async def after_save(self) -> None:
                call_order.append("after")

        xpub = TestXpubOrder(
            id="test123",
            current_balance=1000,
            next_internal_num=0,
            next_external_num=0,
            engine=engine,
        )
        await xpub.save()

        assert call_order == ["before", "after"]

        await engine.close()
