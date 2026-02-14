"""Tests for XPubService — registration, lookup, cache, derivation counters."""

from __future__ import annotations

import pytest

from spv_wallet.bsv.keys import ExtendedKey, xpub_id
from spv_wallet.config.settings import AppConfig, DatabaseConfig
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.errors.definitions import ErrInvalidXPub, ErrMissingFieldXPub, ErrXPubNotFound

# Deterministic test xPub (derived from a known seed)
_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
_MASTER = ExtendedKey.from_seed(_SEED)
_XPUB = _MASTER.neuter().to_string()
_XPUB_ID = xpub_id(_XPUB)


@pytest.fixture
async def engine():
    """Create an initialized engine with in-memory SQLite."""
    config = AppConfig(
        db=DatabaseConfig(engine="sqlite", dsn="sqlite+aiosqlite:///:memory:")
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    yield eng
    await eng.close()


class TestNewXpub:
    """Test xPub registration."""

    async def test_register_xpub(self, engine: SPVWalletEngine) -> None:
        xpub = await engine.xpub_service.new_xpub(_XPUB)
        assert xpub.id == _XPUB_ID
        assert xpub.current_balance == 0
        assert xpub.next_external_num == 0
        assert xpub.next_internal_num == 0

    async def test_register_idempotent(self, engine: SPVWalletEngine) -> None:
        x1 = await engine.xpub_service.new_xpub(_XPUB)
        x2 = await engine.xpub_service.new_xpub(_XPUB)
        assert x1.id == x2.id

    async def test_register_with_metadata(self, engine: SPVWalletEngine) -> None:
        meta = {"label": "test-wallet"}
        xpub = await engine.xpub_service.new_xpub(_XPUB, metadata=meta)
        assert xpub.metadata_["label"] == "test-wallet"

    async def test_missing_xpub_raises(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrMissingFieldXPub)):
            await engine.xpub_service.new_xpub("")

    async def test_invalid_xpub_raises(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrInvalidXPub)):
            await engine.xpub_service.new_xpub("not-a-real-xpub")

    async def test_private_key_rejected(self, engine: SPVWalletEngine) -> None:
        xprv = _MASTER.to_string()  # xprv, not xpub
        with pytest.raises(type(ErrInvalidXPub)):
            await engine.xpub_service.new_xpub(xprv)


class TestGetXpub:
    """Test xPub lookups."""

    async def test_get_xpub(self, engine: SPVWalletEngine) -> None:
        await engine.xpub_service.new_xpub(_XPUB)
        xpub = await engine.xpub_service.get_xpub(_XPUB)
        assert xpub.id == _XPUB_ID

    async def test_get_xpub_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrXPubNotFound)):
            await engine.xpub_service.get_xpub(_XPUB)

    async def test_get_by_id(self, engine: SPVWalletEngine) -> None:
        await engine.xpub_service.new_xpub(_XPUB)
        xpub = await engine.xpub_service.get_xpub_by_id(_XPUB_ID)
        assert xpub is not None
        assert xpub.id == _XPUB_ID

    async def test_get_by_id_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.xpub_service.get_xpub_by_id("nonexistent")
        assert result is None

    async def test_get_by_id_required(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrXPubNotFound)):
            await engine.xpub_service.get_xpub_by_id("nonexistent", required=True)

    async def test_cache_hit(self, engine: SPVWalletEngine) -> None:
        """Second lookup should hit cache."""
        await engine.xpub_service.new_xpub(_XPUB)
        # First lookup populates cache
        await engine.xpub_service.get_xpub_by_id(_XPUB_ID)
        # Verify cache has entry
        cached = await engine.cache.get(f"xpub:{_XPUB_ID}")
        assert cached is not None
        # Second lookup uses cache
        xpub = await engine.xpub_service.get_xpub_by_id(_XPUB_ID)
        assert xpub is not None
        assert xpub.id == _XPUB_ID


class TestUpdateMetadata:
    """Test metadata updates."""

    async def test_update_metadata(self, engine: SPVWalletEngine) -> None:
        await engine.xpub_service.new_xpub(_XPUB, metadata={"a": 1})
        xpub = await engine.xpub_service.update_metadata(_XPUB_ID, {"b": 2})
        assert xpub.metadata_["a"] == 1
        assert xpub.metadata_["b"] == 2

    async def test_update_metadata_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrXPubNotFound)):
            await engine.xpub_service.update_metadata("missing", {"x": 1})


class TestDeleteXpub:
    """Test soft-delete."""

    async def test_delete_xpub(self, engine: SPVWalletEngine) -> None:
        await engine.xpub_service.new_xpub(_XPUB)
        await engine.xpub_service.delete_xpub(_XPUB_ID)
        result = await engine.xpub_service.get_xpub_by_id(_XPUB_ID)
        assert result is None

    async def test_delete_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrXPubNotFound)):
            await engine.xpub_service.delete_xpub("nonexistent")


class TestIncrementChain:
    """Test BIP32 chain counter incrementing."""

    async def test_increment_external(self, engine: SPVWalletEngine) -> None:
        await engine.xpub_service.new_xpub(_XPUB)
        start = await engine.xpub_service.increment_chain(_XPUB_ID, chain=0)
        assert start == 0
        start = await engine.xpub_service.increment_chain(_XPUB_ID, chain=0)
        assert start == 1

    async def test_increment_internal(self, engine: SPVWalletEngine) -> None:
        await engine.xpub_service.new_xpub(_XPUB)
        start = await engine.xpub_service.increment_chain(_XPUB_ID, chain=1)
        assert start == 0
        start = await engine.xpub_service.increment_chain(_XPUB_ID, chain=1)
        assert start == 1

    async def test_increment_batch(self, engine: SPVWalletEngine) -> None:
        await engine.xpub_service.new_xpub(_XPUB)
        start = await engine.xpub_service.increment_chain(
            _XPUB_ID, chain=0, count=5
        )
        assert start == 0
        start = await engine.xpub_service.increment_chain(
            _XPUB_ID, chain=0, count=3
        )
        assert start == 5

    async def test_increment_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrXPubNotFound)):
            await engine.xpub_service.increment_chain("missing", chain=0)
