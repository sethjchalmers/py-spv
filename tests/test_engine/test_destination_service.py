"""Tests for DestinationService — BIP32 address derivation and management."""

from __future__ import annotations

import pytest

from spv_wallet.bsv.keys import ExtendedKey, xpub_id
from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine
from spv_wallet.engine.client import SPVWalletEngine

# Deterministic test xPub
_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
_MASTER = ExtendedKey.from_seed(_SEED)
_XPUB_STR = _MASTER.neuter().to_string()
_XPUB_ID = xpub_id(_XPUB_STR)


@pytest.fixture
async def engine():
    """Create an initialized engine with in-memory SQLite and a registered xPub."""
    config = AppConfig(
        db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    await eng.xpub_service.new_xpub(_XPUB_STR)
    yield eng
    await eng.close()


class TestNewDestination:
    """Test destination derivation."""

    async def test_derive_first_external(self, engine: SPVWalletEngine) -> None:
        dest = await engine.destination_service.new_destination(_XPUB_STR, chain=0)
        assert dest.chain == 0
        assert dest.num == 0
        assert dest.type == "pubkeyhash"
        assert dest.xpub_id == _XPUB_ID
        assert dest.address  # Non-empty BSV address
        assert dest.locking_script  # Non-empty hex
        assert dest.id  # SHA-256 hash

    async def test_derive_sequential(self, engine: SPVWalletEngine) -> None:
        d0 = await engine.destination_service.new_destination(_XPUB_STR, chain=0)
        d1 = await engine.destination_service.new_destination(_XPUB_STR, chain=0)
        assert d0.num == 0
        assert d1.num == 1
        assert d0.address != d1.address

    async def test_derive_internal_chain(self, engine: SPVWalletEngine) -> None:
        dest = await engine.destination_service.new_destination(_XPUB_STR, chain=1)
        assert dest.chain == 1
        assert dest.num == 0

    async def test_derive_with_metadata(self, engine: SPVWalletEngine) -> None:
        meta = {"purpose": "payment"}
        dest = await engine.destination_service.new_destination(_XPUB_STR, metadata=meta)
        assert dest.metadata_["purpose"] == "payment"

    async def test_deterministic_derivation(self, engine: SPVWalletEngine) -> None:
        """Same xpub/chain/num always produces the same address."""
        dest = await engine.destination_service.new_destination(_XPUB_STR, chain=0)
        # Derive at same path manually
        xpub_key = ExtendedKey.from_string(_XPUB_STR)
        child = xpub_key.derive_child(0).derive_child(0)
        from spv_wallet.bsv.address import pubkey_to_address

        expected_addr = pubkey_to_address(child.public_key())
        assert dest.address == expected_addr


class TestNewDestinationAt:
    """Test destination derivation at specific index."""

    async def test_derive_at_specific_index(self, engine: SPVWalletEngine) -> None:
        dest = await engine.destination_service.new_destination_at(_XPUB_STR, chain=0, num=5)
        assert dest.chain == 0
        assert dest.num == 5

    async def test_idempotent(self, engine: SPVWalletEngine) -> None:
        d1 = await engine.destination_service.new_destination_at(_XPUB_STR, chain=0, num=3)
        d2 = await engine.destination_service.new_destination_at(_XPUB_STR, chain=0, num=3)
        assert d1.id == d2.id


class TestGetDestinations:
    """Test destination lookups."""

    async def test_get_by_id(self, engine: SPVWalletEngine) -> None:
        dest = await engine.destination_service.new_destination(_XPUB_STR)
        found = await engine.destination_service.get_destination(dest.id)
        assert found is not None
        assert found.address == dest.address

    async def test_get_by_address(self, engine: SPVWalletEngine) -> None:
        dest = await engine.destination_service.new_destination(_XPUB_STR)
        found = await engine.destination_service.get_destination_by_address(dest.address)
        assert found is not None
        assert found.id == dest.id

    async def test_get_by_xpub(self, engine: SPVWalletEngine) -> None:
        await engine.destination_service.new_destination(_XPUB_STR, chain=0)
        await engine.destination_service.new_destination(_XPUB_STR, chain=0)
        await engine.destination_service.new_destination(_XPUB_STR, chain=1)

        dests = await engine.destination_service.get_destinations_by_xpub(_XPUB_ID)
        assert len(dests) == 3
        # Ordered by chain, num
        assert dests[0].chain == 0 and dests[0].num == 0
        assert dests[1].chain == 0 and dests[1].num == 1
        assert dests[2].chain == 1 and dests[2].num == 0

    async def test_get_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.destination_service.get_destination("nonexistent")
        assert result is None

    async def test_get_address_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.destination_service.get_destination_by_address("nope")
        assert result is None
