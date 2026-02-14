"""Tests for BSV script engine — bsv/script.py."""

from __future__ import annotations

import pytest

from spv_wallet.bsv.keys import ExtendedKey
from spv_wallet.bsv.script import (
    OpCode,
    ScriptType,
    detect_script_type,
    extract_pubkey_hash,
    op_return_script,
    p2pkh_lock_script,
    p2pkh_lock_script_from_pubkey,
    p2pkh_unlock_script,
    push_data,
)
from spv_wallet.utils.crypto import hash160

_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")


class TestPushData:
    """Data push encoding."""

    def test_empty_data(self) -> None:
        result = push_data(b"")
        assert result == bytes([OpCode.OP_0])

    def test_small_push(self) -> None:
        data = b"\xab" * 10
        result = push_data(data)
        assert result[0] == 10
        assert result[1:] == data

    def test_pushdata1(self) -> None:
        data = b"\xab" * 80
        result = push_data(data)
        assert result[0] == OpCode.OP_PUSHDATA1
        assert result[1] == 80
        assert result[2:] == data

    def test_pushdata2(self) -> None:
        data = b"\xab" * 300
        result = push_data(data)
        assert result[0] == OpCode.OP_PUSHDATA2
        import struct

        length = struct.unpack("<H", result[1:3])[0]
        assert length == 300
        assert result[3:] == data

    def test_max_small_push(self) -> None:
        data = b"\x00" * 0x4B
        result = push_data(data)
        assert result[0] == 0x4B


class TestP2PKH:
    """P2PKH locking and unlocking scripts."""

    def test_lock_script_structure(self) -> None:
        pubkey_hash = b"\xab" * 20
        script = p2pkh_lock_script(pubkey_hash)
        assert len(script) == 25
        assert script[0] == OpCode.OP_DUP
        assert script[1] == OpCode.OP_HASH160
        assert script[2] == 0x14  # push 20 bytes
        assert script[3:23] == pubkey_hash
        assert script[23] == OpCode.OP_EQUALVERIFY
        assert script[24] == OpCode.OP_CHECKSIG

    def test_lock_script_invalid_hash(self) -> None:
        with pytest.raises(ValueError, match="20 bytes"):
            p2pkh_lock_script(b"\xab" * 19)

    def test_lock_script_from_pubkey(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pubkey = master.public_key()
        script = p2pkh_lock_script_from_pubkey(pubkey)
        assert len(script) == 25
        expected_hash = hash160(pubkey)
        assert script[3:23] == expected_hash

    def test_unlock_script(self) -> None:
        sig = b"\x30" * 70  # fake DER sig
        pubkey = b"\x02" + b"\x00" * 32  # fake compressed pubkey
        script = p2pkh_unlock_script(sig, pubkey)
        # Should contain push(sig) + push(pubkey)
        assert len(script) > len(sig) + len(pubkey)
        # First byte should be the length of the sig
        assert script[0] == len(sig)


class TestOpReturn:
    """OP_RETURN script construction."""

    def test_single_data(self) -> None:
        script = op_return_script(b"hello")
        assert script[0] == OpCode.OP_FALSE
        assert script[1] == OpCode.OP_RETURN
        # data push follows
        assert script[2] == 5  # push 5 bytes
        assert script[3:8] == b"hello"

    def test_multiple_data(self) -> None:
        script = op_return_script(b"hello", b"world")
        assert script[0] == OpCode.OP_FALSE
        assert script[1] == OpCode.OP_RETURN
        # Two data pushes
        assert script[2] == 5
        assert script[3:8] == b"hello"
        assert script[8] == 5
        assert script[9:14] == b"world"

    def test_empty_data(self) -> None:
        script = op_return_script(b"")
        assert script[0] == OpCode.OP_FALSE
        assert script[1] == OpCode.OP_RETURN
        assert script[2] == OpCode.OP_0  # push empty (OP_0)


class TestScriptTypeDetection:
    """Script type classification."""

    def test_p2pkh(self) -> None:
        pubkey_hash = b"\xab" * 20
        script = p2pkh_lock_script(pubkey_hash)
        assert detect_script_type(script) == ScriptType.P2PKH

    def test_op_return_with_false(self) -> None:
        script = op_return_script(b"data")
        assert detect_script_type(script) == ScriptType.NULL_DATA

    def test_op_return_bare(self) -> None:
        script = bytes([OpCode.OP_RETURN]) + push_data(b"data")
        assert detect_script_type(script) == ScriptType.NULL_DATA

    def test_p2pk_compressed(self) -> None:
        pubkey = b"\x02" + b"\xab" * 32
        script = push_data(pubkey) + bytes([OpCode.OP_CHECKSIG])
        assert detect_script_type(script) == ScriptType.P2PK

    def test_unknown_script(self) -> None:
        script = b"\xff\xfe\xfd"
        assert detect_script_type(script) == ScriptType.UNKNOWN

    def test_empty_script(self) -> None:
        assert detect_script_type(b"") == ScriptType.UNKNOWN


class TestExtractPubkeyHash:
    """Extract pubkey hash from locking scripts."""

    def test_from_p2pkh(self) -> None:
        pubkey_hash = b"\xab" * 20
        script = p2pkh_lock_script(pubkey_hash)
        assert extract_pubkey_hash(script) == pubkey_hash

    def test_from_non_p2pkh(self) -> None:
        script = op_return_script(b"not p2pkh")
        assert extract_pubkey_hash(script) is None
