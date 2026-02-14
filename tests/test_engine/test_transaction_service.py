"""Tests for TransactionService — drafts, recording, callbacks, queries."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from spv_wallet.bsv.keys import ExtendedKey, xpub_id
from spv_wallet.bsv.script import p2pkh_lock_script
from spv_wallet.bsv.transaction import Transaction as BsvTransaction
from spv_wallet.chain.arc.models import FeeUnit, TXInfo, TXStatus
from spv_wallet.config.settings import AppConfig, DatabaseConfig
from spv_wallet.engine.client import SPVWalletEngine
from spv_wallet.engine.services.transaction_service import (
    ErrDraftCanceled,
    ErrInvalidHex,
    TransactionService,
    _DEFAULT_FEE_UNIT,
    _INPUT_SIZE,
    _OUTPUT_SIZE,
    _TX_OVERHEAD,
)
from spv_wallet.errors.definitions import (
    ErrDraftNotFound,
    ErrNotEnoughFunds,
    ErrTransactionNotFound,
)

# Deterministic test xPub (from known seed — same as test_xpub_service.py)
_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
_MASTER = ExtendedKey.from_seed(_SEED)
_XPUB = _MASTER.neuter().to_string()
_XPUB_ID = xpub_id(_XPUB)
_TX_ID = "a" * 64
_P2PKH_SCRIPT = "76a914" + "ab" * 20 + "88ac"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def engine():
    config = AppConfig(
        db=DatabaseConfig(engine="sqlite", dsn="sqlite+aiosqlite:///:memory:")
    )
    eng = SPVWalletEngine(config)
    await eng.initialize()
    # Register the test xPub so draft creation can find it
    await eng.xpub_service.new_xpub(_XPUB)
    yield eng
    await eng.close()


async def _seed_utxos(engine: SPVWalletEngine, count: int = 5, sats: int = 10000):
    """Seed UTXOs for tests."""
    for i in range(count):
        await engine.utxo_service.new_utxo(
            _XPUB_ID, _TX_ID, i, sats, _P2PKH_SCRIPT,
        )


# ---------------------------------------------------------------------------
# Fee estimation (unit test — no DB needed)
# ---------------------------------------------------------------------------


class TestFeeEstimation:
    def test_estimate_fee_single_input_output(self):
        svc = TransactionService.__new__(TransactionService)
        fee = svc._estimate_fee(input_count=1, output_count=1, fee_unit=_DEFAULT_FEE_UNIT)
        expected_size = _TX_OVERHEAD + _INPUT_SIZE + _OUTPUT_SIZE
        assert fee == _DEFAULT_FEE_UNIT.fee_for_size(expected_size)
        assert fee >= 1

    def test_estimate_fee_multiple(self):
        svc = TransactionService.__new__(TransactionService)
        fee = svc._estimate_fee(input_count=3, output_count=2, fee_unit=FeeUnit(1, 1000))
        expected_size = _TX_OVERHEAD + (3 * _INPUT_SIZE) + (2 * _OUTPUT_SIZE)
        assert fee == FeeUnit(1, 1000).fee_for_size(expected_size)


# ---------------------------------------------------------------------------
# Output processing (unit test)
# ---------------------------------------------------------------------------


class TestProcessOutputs:
    def test_address_output(self):
        svc = TransactionService.__new__(TransactionService)
        outputs = [{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 5000}]
        tx_outs, total = svc._process_outputs(outputs)
        assert len(tx_outs) == 1
        assert total == 5000
        assert len(tx_outs[0].script_pubkey) == 25  # P2PKH script

    def test_op_return_output(self):
        svc = TransactionService.__new__(TransactionService)
        outputs = [{"op_return": "deadbeef"}]
        tx_outs, total = svc._process_outputs(outputs)
        assert len(tx_outs) == 1
        assert total == 0  # OP_RETURN has no value
        assert tx_outs[0].value == 0

    def test_raw_script_output(self):
        svc = TransactionService.__new__(TransactionService)
        outputs = [{"script": _P2PKH_SCRIPT, "satoshis": 3000}]
        tx_outs, total = svc._process_outputs(outputs)
        assert total == 3000
        assert tx_outs[0].script_pubkey == bytes.fromhex(_P2PKH_SCRIPT)

    def test_mixed_outputs(self):
        svc = TransactionService.__new__(TransactionService)
        outputs = [
            {"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000},
            {"op_return": "aa"},
            {"script": _P2PKH_SCRIPT, "satoshis": 2000},
        ]
        tx_outs, total = svc._process_outputs(outputs)
        assert len(tx_outs) == 3
        assert total == 3000


# ---------------------------------------------------------------------------
# Draft creation (integration — uses engine + DB)
# ---------------------------------------------------------------------------


class TestNewTransaction:
    async def test_create_draft(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=3, sats=20000)

        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 5000}],
        )
        assert draft.status == "draft"
        assert draft.xpub_id == _XPUB_ID
        assert draft.total_value == 5000
        assert draft.fee > 0
        assert draft.hex_body != ""
        assert draft.configuration is not None
        assert "inputs" in draft.configuration
        assert "outputs" in draft.configuration
        assert "fee" in draft.configuration

    async def test_create_draft_custom_fee(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=2, sats=50000)

        fee_unit = FeeUnit(satoshis=5, bytes=1000)
        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000}],
            fee_unit=fee_unit,
        )
        # Fee should be higher with 5 sat/1000 bytes
        assert draft.fee > 0
        assert draft.configuration["fee_unit"]["satoshis"] == 5

    async def test_create_draft_insufficient_funds(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=1, sats=100)

        with pytest.raises(type(ErrNotEnoughFunds)):
            await engine.transaction_service.new_transaction(
                _XPUB_ID,
                outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 99999}],
            )

    async def test_draft_reserves_utxos(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=2, sats=50000)

        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000}],
        )

        # Check that UTXOs have been reserved
        config = draft.configuration
        for inp in config["inputs"]:
            utxo = await engine.utxo_service.get_utxo(inp["utxo_id"])
            assert utxo is not None
            assert utxo.draft_id == draft.id

    async def test_draft_with_metadata(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=2, sats=50000)

        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000}],
            metadata={"note": "test payment"},
        )
        assert draft.metadata_["note"] == "test payment"


# ---------------------------------------------------------------------------
# Cancel draft
# ---------------------------------------------------------------------------


class TestCancelDraft:
    async def test_cancel_draft(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=2, sats=50000)

        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000}],
        )

        await engine.transaction_service.cancel_draft(draft.id, _XPUB_ID)

        # Draft should be canceled
        d = await engine.transaction_service.get_draft(draft.id)
        assert d is not None
        assert d.status == "canceled"

        # UTXOs should be released
        config = draft.configuration
        for inp in config["inputs"]:
            utxo = await engine.utxo_service.get_utxo(inp["utxo_id"])
            assert utxo is not None
            assert utxo.draft_id == ""

    async def test_cancel_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrDraftNotFound)):
            await engine.transaction_service.cancel_draft("nonexistent", _XPUB_ID)


# ---------------------------------------------------------------------------
# Record transaction
# ---------------------------------------------------------------------------


class TestRecordTransaction:
    async def test_record_simple_tx(self, engine: SPVWalletEngine) -> None:
        # Build a simple transaction manually
        bsv_tx = BsvTransaction()
        bsv_tx.add_input(
            prev_tx_id=bytes.fromhex(_TX_ID)[::-1],
            prev_tx_out_index=0,
            script_sig=b"\x00" * 72 + b"\x00" * 33,  # dummy sig+pubkey
        )
        bsv_tx.add_output(5000, bytes.fromhex(_P2PKH_SCRIPT))
        hex_body = bsv_tx.to_hex()

        tx = await engine.transaction_service.record_transaction(
            _XPUB_ID, hex_body,
        )
        assert tx.id == bsv_tx.txid()
        assert tx.status == "created"
        assert tx.direction == "outgoing"
        assert tx.number_of_inputs == 1
        assert tx.number_of_outputs == 1

    async def test_record_with_draft(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=2, sats=50000)

        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000}],
        )

        # Build a tx that would be the signed version
        bsv_tx = BsvTransaction()
        bsv_tx.add_input(
            prev_tx_id=bytes.fromhex(_TX_ID)[::-1],
            prev_tx_out_index=0,
            script_sig=b"\x00" * 105,
        )
        bsv_tx.add_output(1000, bytes.fromhex(_P2PKH_SCRIPT))
        hex_body = bsv_tx.to_hex()

        tx = await engine.transaction_service.record_transaction(
            _XPUB_ID, hex_body, draft_id=draft.id,
        )
        assert tx.id == bsv_tx.txid()

        # Draft should be marked complete
        d = await engine.transaction_service.get_draft(draft.id)
        assert d is not None
        assert d.status == "complete"
        assert d.final_tx_id == tx.id

    async def test_record_invalid_hex(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrInvalidHex)):
            await engine.transaction_service.record_transaction(
                _XPUB_ID, "not_valid_hex!!",
            )

    async def test_record_idempotent(self, engine: SPVWalletEngine) -> None:
        bsv_tx = BsvTransaction()
        bsv_tx.add_input(bytes(32), 0)
        bsv_tx.add_output(1000, bytes.fromhex(_P2PKH_SCRIPT))
        hex_body = bsv_tx.to_hex()

        tx1 = await engine.transaction_service.record_transaction(_XPUB_ID, hex_body)
        tx2 = await engine.transaction_service.record_transaction(_XPUB_ID, hex_body)
        assert tx1.id == tx2.id

    async def test_record_canceled_draft(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=2, sats=50000)

        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000}],
        )
        await engine.transaction_service.cancel_draft(draft.id, _XPUB_ID)

        bsv_tx = BsvTransaction()
        bsv_tx.add_input(bytes(32), 0, script_sig=b"\x00" * 72)
        bsv_tx.add_output(1000, bytes.fromhex(_P2PKH_SCRIPT))

        with pytest.raises(type(ErrDraftCanceled)):
            await engine.transaction_service.record_transaction(
                _XPUB_ID, bsv_tx.to_hex(), draft_id=draft.id,
            )

    async def test_record_with_metadata(self, engine: SPVWalletEngine) -> None:
        bsv_tx = BsvTransaction()
        bsv_tx.add_input(bytes.fromhex("bb" * 32), 0)
        bsv_tx.add_output(1000, bytes.fromhex(_P2PKH_SCRIPT))

        tx = await engine.transaction_service.record_transaction(
            _XPUB_ID, bsv_tx.to_hex(),
            metadata={"purpose": "test"},
        )
        assert tx.metadata_["purpose"] == "test"


# ---------------------------------------------------------------------------
# ARC Callback handling
# ---------------------------------------------------------------------------


class TestHandleARCCallback:
    async def _create_tx(self, engine: SPVWalletEngine) -> str:
        bsv_tx = BsvTransaction()
        bsv_tx.add_input(bytes.fromhex("cc" * 32), 0)
        bsv_tx.add_output(1000, bytes.fromhex(_P2PKH_SCRIPT))
        tx = await engine.transaction_service.record_transaction(
            _XPUB_ID, bsv_tx.to_hex(),
        )
        return tx.id

    async def test_callback_seen_on_network(self, engine: SPVWalletEngine) -> None:
        txid = await self._create_tx(engine)
        tx = await engine.transaction_service.handle_arc_callback(
            txid, "SEEN_ON_NETWORK",
        )
        assert tx is not None
        assert tx.status == "seen_on_network"

    async def test_callback_mined(self, engine: SPVWalletEngine) -> None:
        txid = await self._create_tx(engine)
        tx = await engine.transaction_service.handle_arc_callback(
            txid, "MINED",
            block_hash="block_hash_here",
            block_height=800000,
            merkle_path="merkle_data",
        )
        assert tx is not None
        assert tx.status == "mined"
        assert tx.block_hash == "block_hash_here"
        assert tx.block_height == 800000
        assert tx.merkle_path == "merkle_data"

    async def test_callback_confirmed(self, engine: SPVWalletEngine) -> None:
        txid = await self._create_tx(engine)
        tx = await engine.transaction_service.handle_arc_callback(txid, "CONFIRMED")
        assert tx is not None
        assert tx.status == "mined"  # CONFIRMED maps to "mined"

    async def test_callback_rejected_with_competing(self, engine: SPVWalletEngine) -> None:
        txid = await self._create_tx(engine)
        tx = await engine.transaction_service.handle_arc_callback(
            txid, "REJECTED",
            competing_txs=["tx1", "tx2"],
        )
        assert tx is not None
        assert tx.status == "rejected"
        assert tx.metadata_.get("competing_txs") == ["tx1", "tx2"]

    async def test_callback_broadcast(self, engine: SPVWalletEngine) -> None:
        txid = await self._create_tx(engine)
        tx = await engine.transaction_service.handle_arc_callback(
            txid, "ACCEPTED_BY_NETWORK",
        )
        assert tx is not None
        assert tx.status == "broadcast"

    async def test_callback_unknown_tx(self, engine: SPVWalletEngine) -> None:
        result = await engine.transaction_service.handle_arc_callback(
            "nonexistent_txid", "MINED",
        )
        assert result is None

    async def test_callback_unknown_status_no_change(self, engine: SPVWalletEngine) -> None:
        txid = await self._create_tx(engine)
        tx = await engine.transaction_service.handle_arc_callback(txid, "QUEUED")
        assert tx is not None
        assert tx.status == "created"  # No mapping for QUEUED, status unchanged


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestTransactionQueries:
    async def _create_txs(self, engine: SPVWalletEngine, count: int = 3) -> list[str]:
        ids = []
        for i in range(count):
            bsv_tx = BsvTransaction()
            bsv_tx.add_input(bytes.fromhex(f"{i:064x}"), 0)
            bsv_tx.add_output(1000 * (i + 1), bytes.fromhex(_P2PKH_SCRIPT))
            tx = await engine.transaction_service.record_transaction(
                _XPUB_ID, bsv_tx.to_hex(),
            )
            ids.append(tx.id)
        return ids

    async def test_get_transaction(self, engine: SPVWalletEngine) -> None:
        ids = await self._create_txs(engine, 1)
        tx = await engine.transaction_service.get_transaction(ids[0])
        assert tx is not None
        assert tx.id == ids[0]

    async def test_get_transaction_not_found(self, engine: SPVWalletEngine) -> None:
        tx = await engine.transaction_service.get_transaction("nope")
        assert tx is None

    async def test_get_transactions(self, engine: SPVWalletEngine) -> None:
        await self._create_txs(engine, 3)
        txs = await engine.transaction_service.get_transactions(_XPUB_ID)
        assert len(txs) == 3

    async def test_get_transactions_filter_status(self, engine: SPVWalletEngine) -> None:
        ids = await self._create_txs(engine, 2)
        # Update one status
        await engine.transaction_service.handle_arc_callback(ids[0], "MINED")

        mined = await engine.transaction_service.get_transactions(_XPUB_ID, status="mined")
        assert len(mined) == 1
        assert mined[0].id == ids[0]

    async def test_get_draft(self, engine: SPVWalletEngine) -> None:
        await _seed_utxos(engine, count=2, sats=50000)
        draft = await engine.transaction_service.new_transaction(
            _XPUB_ID,
            outputs=[{"to": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "satoshis": 1000}],
        )
        result = await engine.transaction_service.get_draft(draft.id)
        assert result is not None
        assert result.id == draft.id

    async def test_get_draft_not_found(self, engine: SPVWalletEngine) -> None:
        result = await engine.transaction_service.get_draft("nope")
        assert result is None


# ---------------------------------------------------------------------------
# Update status
# ---------------------------------------------------------------------------


class TestUpdateTransactionStatus:
    async def test_update_status(self, engine: SPVWalletEngine) -> None:
        bsv_tx = BsvTransaction()
        bsv_tx.add_input(bytes.fromhex("dd" * 32), 0)
        bsv_tx.add_output(1000, bytes.fromhex(_P2PKH_SCRIPT))
        tx = await engine.transaction_service.record_transaction(
            _XPUB_ID, bsv_tx.to_hex(),
        )

        updated = await engine.transaction_service.update_transaction_status(
            tx.id, "mined",
        )
        assert updated.status == "mined"

    async def test_update_status_not_found(self, engine: SPVWalletEngine) -> None:
        with pytest.raises(type(ErrTransactionNotFound)):
            await engine.transaction_service.update_transaction_status(
                "nope", "mined",
            )


# ---------------------------------------------------------------------------
# Internal: _get_fee_unit
# ---------------------------------------------------------------------------


class TestGetFeeUnit:
    async def test_fallback_no_chain(self, engine: SPVWalletEngine) -> None:
        """Without chain service or with failed chain, uses default fee unit."""
        # Force chain_service to None so we get the default fallback
        engine._chain = None
        svc = engine.transaction_service
        fee_unit = await svc._get_fee_unit()
        assert fee_unit == _DEFAULT_FEE_UNIT
