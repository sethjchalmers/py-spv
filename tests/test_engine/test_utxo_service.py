"""Tests for UTXOService — CRUD, filtering, balance, and spending."""

from __future__ import annotations

import pytest

from spv_wallet.config.settings import AppConfig, DatabaseConfig, DatabaseEngine
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.errors.definitions import ErrNotEnoughFunds, ErrUTXONotFound

_XPUB_ID = "x" * 64
_TX_ID = "a" * 64


@pytest.fixture
async def engine():
    config = AppConfig(
        db=DatabaseConfig(engine=DatabaseEngine.SQLITE, dsn="sqlite+aiosqlite:///:memory:")
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    yield eng
    await eng.close()


class TestNewUTXO:
    """Test UTXO creation."""

    async def test_create_utxo(self, engine: SPVWalletEngine) -> None:
        utxo = await engine.utxo_service.new_utxo(
            xpub_id=_XPUB_ID,
            transaction_id=_TX_ID,
            output_index=0,
            satoshis=50000,
            script_pub_key="76a914" + "ab" * 20 + "88ac",
        )
        assert utxo.id == f"{_TX_ID}:0"
        assert utxo.satoshis == 50000
        assert not utxo.is_spent

    async def test_create_idempotent(self, engine: SPVWalletEngine) -> None:
        u1 = await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, 0, 50000, "script")
        u2 = await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, 0, 50000, "script")
        assert u1.id == u2.id

    async def test_create_with_metadata(self, engine: SPVWalletEngine) -> None:
        utxo = await engine.utxo_service.new_utxo(
            _XPUB_ID,
            _TX_ID,
            0,
            50000,
            "script",
            metadata={"source": "mining"},
        )
        assert utxo.metadata_["source"] == "mining"


class TestGetUTXO:
    """Test UTXO lookups."""

    async def test_get_utxo(self, engine: SPVWalletEngine) -> None:
        await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, 0, 50000, "s")
        utxo = await engine.utxo_service.get_utxo(f"{_TX_ID}:0")
        assert utxo is not None
        assert utxo.satoshis == 50000

    async def test_get_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.utxo_service.get_utxo("nonexistent:0")
        assert result is None


class TestGetUTXOs:
    """Test filtered queries."""

    async def _seed_utxos(self, engine: SPVWalletEngine) -> None:
        for i in range(3):
            await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, i, 1000 * (i + 1), "script")
        # Different xpub
        await engine.utxo_service.new_utxo("y" * 64, _TX_ID, 10, 9999, "s")
        # Spent UTXO
        utxo = await engine.utxo_service.new_utxo(_XPUB_ID, "b" * 64, 0, 500, "script")
        await engine.utxo_service.mark_spent(utxo.id, "c" * 64)

    async def test_get_all(self, engine: SPVWalletEngine) -> None:
        await self._seed_utxos(engine)
        utxos = await engine.utxo_service.get_utxos()
        assert len(utxos) == 5

    async def test_filter_by_xpub(self, engine: SPVWalletEngine) -> None:
        await self._seed_utxos(engine)
        utxos = await engine.utxo_service.get_utxos(xpub_id=_XPUB_ID)
        assert len(utxos) == 4  # 3 unspent + 1 spent

    async def test_filter_unspent(self, engine: SPVWalletEngine) -> None:
        await self._seed_utxos(engine)
        utxos = await engine.utxo_service.get_utxos(xpub_id=_XPUB_ID, unspent_only=True)
        assert len(utxos) == 3
        for u in utxos:
            assert not u.is_spent

    async def test_filter_by_transaction(self, engine: SPVWalletEngine) -> None:
        await self._seed_utxos(engine)
        utxos = await engine.utxo_service.get_utxos(transaction_id=_TX_ID)
        assert len(utxos) == 4  # 3 for xpub + 1 for other xpub

    async def test_ordered_by_satoshis_desc(self, engine: SPVWalletEngine) -> None:
        await self._seed_utxos(engine)
        utxos = await engine.utxo_service.get_utxos(xpub_id=_XPUB_ID, unspent_only=True)
        sats = [u.satoshis for u in utxos]
        assert sats == sorted(sats, reverse=True)


class TestCountUTXOs:
    """Test counting."""

    async def test_count_all(self, engine: SPVWalletEngine) -> None:
        for i in range(5):
            await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, i, 1000, "s")
        assert await engine.utxo_service.count_utxos(xpub_id=_XPUB_ID) == 5

    async def test_count_unspent(self, engine: SPVWalletEngine) -> None:
        for i in range(3):
            await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, i, 1000, "s")
        await engine.utxo_service.mark_spent(f"{_TX_ID}:0", "spent_tx")
        assert await engine.utxo_service.count_utxos(xpub_id=_XPUB_ID, unspent_only=True) == 2


class TestMarkSpent:
    """Test spending."""

    async def test_mark_spent(self, engine: SPVWalletEngine) -> None:
        await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, 0, 50000, "s")
        utxo = await engine.utxo_service.mark_spent(f"{_TX_ID}:0", "spending_tx")
        assert utxo.is_spent
        assert utxo.spending_tx_id == "spending_tx"

    async def test_mark_spent_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrUTXONotFound)):
            await engine.utxo_service.mark_spent("nope:0", "tx")


class TestBalance:
    """Test balance aggregation."""

    async def test_balance(self, engine: SPVWalletEngine) -> None:
        for i in range(3):
            await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, i, 1000 * (i + 1), "s")
        # 1000 + 2000 + 3000 = 6000
        balance = await engine.utxo_service.get_balance(_XPUB_ID)
        assert balance == 6000

    async def test_balance_excludes_spent(self, engine: SPVWalletEngine) -> None:
        await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, 0, 5000, "s")
        await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, 1, 3000, "s")
        await engine.utxo_service.mark_spent(f"{_TX_ID}:0", "tx")
        balance = await engine.utxo_service.get_balance(_XPUB_ID)
        assert balance == 3000

    async def test_balance_zero_no_utxos(self, engine: SPVWalletEngine) -> None:
        balance = await engine.utxo_service.get_balance(_XPUB_ID)
        assert balance == 0


class TestUnspentForDraft:
    """Test UTXO selection for drafts."""

    async def test_select_utxos(self, engine: SPVWalletEngine) -> None:
        for i in range(5):
            await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, i, 1000, "s")
        selected = await engine.utxo_service.get_unspent_for_draft(_XPUB_ID, required_sats=2500)
        total = sum(u.satoshis for u in selected)
        assert total >= 2500

    async def test_insufficient_funds(self, engine: SPVWalletEngine) -> None:
        await engine.utxo_service.new_utxo(_XPUB_ID, _TX_ID, 0, 100, "s")
        with pytest.raises(type(ErrNotEnoughFunds)):
            await engine.utxo_service.get_unspent_for_draft(_XPUB_ID, required_sats=500)
