"""Tests for transaction primitives — bsv/transaction.py."""

from __future__ import annotations

import struct
from io import BytesIO

import pytest

from spv_wallet.bsv.script import op_return_script, p2pkh_lock_script
from spv_wallet.bsv.transaction import (
    COINBASE_TXID,
    DEFAULT_SEQUENCE,
    Transaction,
    TxInput,
    TxOutput,
    encode_varint,
    read_varint,
)


class TestVarInt:
    """Variable-length integer encoding/decoding."""

    @pytest.mark.parametrize(
        ("value", "expected_len"),
        [
            (0, 1),
            (1, 1),
            (252, 1),
            (253, 3),
            (0xFFFF, 3),
            (0x10000, 5),
            (0xFFFFFFFF, 5),
            (0x100000000, 9),
        ],
    )
    def test_encode_length(self, value: int, expected_len: int) -> None:
        encoded = encode_varint(value)
        assert len(encoded) == expected_len

    @pytest.mark.parametrize(
        "value",
        [0, 1, 100, 252, 253, 1000, 65535, 65536, 100000, 0xFFFFFFFF, 0x100000000],
    )
    def test_roundtrip(self, value: int) -> None:
        encoded = encode_varint(value)
        stream = BytesIO(encoded)
        decoded = read_varint(stream)
        assert decoded == value

    def test_read_empty_stream(self) -> None:
        stream = BytesIO(b"")
        with pytest.raises(ValueError, match="end of stream"):
            read_varint(stream)


class TestTxInput:
    """Transaction input serialization."""

    def test_serialize_deserialize(self) -> None:
        inp = TxInput(
            prev_tx_id=b"\xab" * 32,
            prev_tx_out_index=1,
            script_sig=b"\xcd" * 10,
            sequence=DEFAULT_SEQUENCE,
        )
        data = inp.serialize()
        stream = BytesIO(data)
        restored = TxInput.deserialize(stream)
        assert restored.prev_tx_id == inp.prev_tx_id
        assert restored.prev_tx_out_index == inp.prev_tx_out_index
        assert restored.script_sig == inp.script_sig
        assert restored.sequence == inp.sequence

    def test_prev_tx_id_hex(self) -> None:
        txid_internal = bytes.fromhex(
            "abcd" * 16
        )
        inp = TxInput(prev_tx_id=txid_internal, prev_tx_out_index=0)
        # Display hex should be reversed
        assert inp.prev_tx_id_hex == txid_internal[::-1].hex()

    def test_is_coinbase(self) -> None:
        coinbase = TxInput(
            prev_tx_id=COINBASE_TXID,
            prev_tx_out_index=0xFFFFFFFF,
        )
        assert coinbase.is_coinbase

    def test_is_not_coinbase(self) -> None:
        regular = TxInput(
            prev_tx_id=b"\xab" * 32,
            prev_tx_out_index=0,
        )
        assert not regular.is_coinbase

    def test_empty_script_sig(self) -> None:
        inp = TxInput(prev_tx_id=b"\x00" * 32, prev_tx_out_index=0)
        assert inp.script_sig == b""
        data = inp.serialize()
        restored = TxInput.deserialize(BytesIO(data))
        assert restored.script_sig == b""


class TestTxOutput:
    """Transaction output serialization."""

    def test_serialize_deserialize(self) -> None:
        script = p2pkh_lock_script(b"\xab" * 20)
        out = TxOutput(value=50000, script_pubkey=script)
        data = out.serialize()
        stream = BytesIO(data)
        restored = TxOutput.deserialize(stream)
        assert restored.value == out.value
        assert restored.script_pubkey == out.script_pubkey

    def test_zero_value(self) -> None:
        out = TxOutput(value=0, script_pubkey=op_return_script(b"test"))
        data = out.serialize()
        restored = TxOutput.deserialize(BytesIO(data))
        assert restored.value == 0


class TestTransaction:
    """Full transaction serialization and deserialization."""

    def _make_simple_tx(self) -> Transaction:
        """Create a simple transaction for testing."""
        tx = Transaction(version=1, locktime=0)
        tx.add_input(b"\xab" * 32, 0, b"\xcd" * 20)
        tx.add_output(50000, p2pkh_lock_script(b"\xef" * 20))
        return tx

    def test_serialize_deserialize(self) -> None:
        tx = self._make_simple_tx()
        raw = tx.serialize()
        restored = Transaction.from_bytes(raw)
        assert restored.version == tx.version
        assert restored.locktime == tx.locktime
        assert len(restored.inputs) == len(tx.inputs)
        assert len(restored.outputs) == len(tx.outputs)
        assert restored.inputs[0].prev_tx_id == tx.inputs[0].prev_tx_id
        assert restored.outputs[0].value == tx.outputs[0].value
        assert restored.outputs[0].script_pubkey == tx.outputs[0].script_pubkey

    def test_hex_roundtrip(self) -> None:
        tx = self._make_simple_tx()
        hex_str = tx.to_hex()
        restored = Transaction.from_hex(hex_str)
        assert restored.to_hex() == hex_str

    def test_txid_deterministic(self) -> None:
        tx = self._make_simple_tx()
        txid1 = tx.txid()
        txid2 = tx.txid()
        assert txid1 == txid2
        assert len(txid1) == 64

    def test_txid_changes_with_inputs(self) -> None:
        tx1 = self._make_simple_tx()
        tx2 = self._make_simple_tx()
        tx2.add_input(b"\x11" * 32, 1)
        assert tx1.txid() != tx2.txid()

    def test_txid_bytes(self) -> None:
        tx = self._make_simple_tx()
        txid_hex = tx.txid()
        txid_b = tx.txid_bytes()
        assert len(txid_b) == 32
        # txid hex is reversed byte order
        assert txid_b[::-1].hex() == txid_hex

    def test_size(self) -> None:
        tx = self._make_simple_tx()
        assert tx.size == len(tx.serialize())
        assert tx.size > 0

    def test_add_input(self) -> None:
        tx = Transaction()
        assert len(tx.inputs) == 0
        inp = tx.add_input(b"\x00" * 32, 0)
        assert len(tx.inputs) == 1
        assert isinstance(inp, TxInput)

    def test_add_output(self) -> None:
        tx = Transaction()
        assert len(tx.outputs) == 0
        out = tx.add_output(1000, b"\x00" * 25)
        assert len(tx.outputs) == 1
        assert isinstance(out, TxOutput)

    def test_multiple_inputs_outputs(self) -> None:
        tx = Transaction()
        for i in range(5):
            tx.add_input(bytes([i]) * 32, i)
        for i in range(3):
            tx.add_output(1000 * (i + 1), p2pkh_lock_script(bytes([i]) * 20))
        raw = tx.serialize()
        restored = Transaction.from_bytes(raw)
        assert len(restored.inputs) == 5
        assert len(restored.outputs) == 3
        assert restored.outputs[2].value == 3000

    def test_version_2(self) -> None:
        tx = Transaction(version=2)
        tx.add_input(b"\x00" * 32, 0)
        tx.add_output(1000, b"\x00")
        raw = tx.serialize()
        restored = Transaction.from_bytes(raw)
        assert restored.version == 2

    def test_locktime(self) -> None:
        tx = Transaction(locktime=500000)
        tx.add_input(b"\x00" * 32, 0)
        tx.add_output(1000, b"\x00")
        raw = tx.serialize()
        restored = Transaction.from_bytes(raw)
        assert restored.locktime == 500000

    def test_op_return_output(self) -> None:
        tx = Transaction()
        tx.add_input(b"\x00" * 32, 0)
        tx.add_output(0, op_return_script(b"hello BSV"))
        raw = tx.serialize()
        restored = Transaction.from_bytes(raw)
        assert restored.outputs[0].value == 0

    def test_known_coinbase_tx(self) -> None:
        """Verify that a transaction with known structure serializes correctly."""
        # Build a minimal coinbase-like tx
        tx = Transaction(version=1, locktime=0)
        tx.add_input(COINBASE_TXID, 0xFFFFFFFF, b"\x04" + b"\xff" * 3)
        tx.add_output(5000000000, p2pkh_lock_script(b"\xab" * 20))
        raw = tx.serialize()
        # Version should be first 4 bytes LE
        assert struct.unpack("<i", raw[:4])[0] == 1
        # Should roundtrip cleanly
        restored = Transaction.from_bytes(raw)
        assert restored.inputs[0].is_coinbase
        assert restored.outputs[0].value == 5000000000
