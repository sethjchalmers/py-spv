"""Edge-case tests to reach >90% branch coverage on BSV modules."""

from __future__ import annotations

import struct
from io import BytesIO

import pytest

from spv_wallet.bsv.address import (
    address_to_pubkey_hash,
    privkey_to_wif,
    validate_address,
    wif_to_privkey,
)
from spv_wallet.bsv.keys import (
    ExtendedKey,
    base58check_encode,
    decompress_public_key,
    private_key_to_public_key,
    sign_message,
    verify_signature,
)
from spv_wallet.bsv.script import (
    ScriptType,
    detect_script_type,
    push_data,
    OpCode,
)
from spv_wallet.bsv.transaction import TxInput


# ---------------------------------------------------------------------------
# keys.py edge cases
# ---------------------------------------------------------------------------

_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")


class TestDecompressErrors:
    def test_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="Invalid compressed key length"):
            decompress_public_key(b"\x02" + b"\x00" * 10)

    def test_bad_prefix(self) -> None:
        with pytest.raises(ValueError, match="Invalid compressed key prefix"):
            decompress_public_key(b"\x05" + b"\x00" * 32)


class TestVerifySignatureEdgeCases:
    def test_uncompressed_pubkey(self) -> None:
        """verify_signature should accept 65-byte uncompressed pubkey."""
        privkey = ExtendedKey.from_seed(_SEED).key
        pubkey_compressed = private_key_to_public_key(privkey, compressed=True)
        uncompressed = decompress_public_key(pubkey_compressed)
        msg_hash = b"\xaa" * 32
        sig = sign_message(privkey, msg_hash)
        assert verify_signature(uncompressed, msg_hash, sig)

    def test_raw_64byte_pubkey(self) -> None:
        """verify_signature should accept 64-byte raw pubkey (no prefix)."""
        privkey = ExtendedKey.from_seed(_SEED).key
        pubkey_compressed = private_key_to_public_key(privkey, compressed=True)
        uncompressed = decompress_public_key(pubkey_compressed)
        raw = uncompressed[1:]  # 64 bytes, no prefix
        msg_hash = b"\xbb" * 32
        sig = sign_message(privkey, msg_hash)
        assert verify_signature(raw, msg_hash, sig)

    def test_bad_signature_returns_false(self) -> None:
        privkey = ExtendedKey.from_seed(_SEED).key
        pubkey = private_key_to_public_key(privkey, compressed=True)
        assert not verify_signature(pubkey, b"\xcc" * 32, b"\x30\x06\x02\x01\x01\x02\x01\x01")


class TestExtendedKeyEdgeCases:
    def test_from_string_invalid_length(self) -> None:
        # Create a valid Base58Check string but with wrong payload length
        short = base58check_encode(b"\x04\x88\xb2\x1e" + b"\x00" * 70)
        with pytest.raises(ValueError, match="Invalid extended key length"):
            ExtendedKey.from_string(short)

    def test_from_string_unknown_version(self) -> None:
        payload = b"\xff\xff\xff\xff" + b"\x00" * 74
        encoded = base58check_encode(payload)
        with pytest.raises(ValueError, match="Unknown version bytes"):
            ExtendedKey.from_string(encoded)

    def test_from_seed_too_short(self) -> None:
        with pytest.raises(ValueError, match="Seed must be"):
            ExtendedKey.from_seed(b"\x00" * 10)

    def test_from_seed_too_long(self) -> None:
        with pytest.raises(ValueError, match="Seed must be"):
            ExtendedKey.from_seed(b"\x00" * 100)

    def test_hardened_from_public_key_raises(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pub = master.neuter()
        with pytest.raises(ValueError, match="Cannot derive hardened child"):
            pub.derive_child(0x80000000)

    def test_public_key_derivation(self) -> None:
        """Public child derivation from xpub (non-hardened)."""
        master = ExtendedKey.from_seed(_SEED)
        pub_master = master.neuter()
        child_pub = pub_master.derive_child(0)
        assert not child_pub.is_private
        assert child_pub.depth == 1

    def test_neuter_public_is_identity(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pub = master.neuter()
        assert pub.neuter() is pub  # identity, returns self


# ---------------------------------------------------------------------------
# address.py edge cases
# ---------------------------------------------------------------------------


class TestAddressEdgeCases:
    def test_address_to_pubkey_hash_invalid(self) -> None:
        # Encode a valid Base58Check but with only 10 payload bytes
        payload = b"\x00" * 10
        bad_addr = base58check_encode(payload)
        with pytest.raises(ValueError, match="Invalid address payload"):
            address_to_pubkey_hash(bad_addr)

    def test_wif_to_privkey_invalid_length(self) -> None:
        # Encode only 20 bytes (needs 33 or 34)
        payload = b"\x80" + b"\x00" * 19
        bad_wif = base58check_encode(payload)
        with pytest.raises(ValueError, match="Invalid WIF payload"):
            wif_to_privkey(bad_wif)

    def test_uncompressed_wif_roundtrip(self) -> None:
        """privkey_to_wif with compressed=False and back."""
        privkey = ExtendedKey.from_seed(_SEED).key
        wif = privkey_to_wif(privkey, compressed=False)
        recovered, compressed, testnet = wif_to_privkey(wif)
        assert recovered == privkey
        assert not compressed
        assert not testnet

    def test_validate_invalid_address(self) -> None:
        assert not validate_address("not-a-valid-address")


# ---------------------------------------------------------------------------
# script.py edge cases
# ---------------------------------------------------------------------------


class TestScriptEdgeCases:
    def test_push_data_op_pushdata4(self) -> None:
        """Data > 0xFFFF bytes should use OP_PUSHDATA4."""
        big_data = b"\xab" * 0x10000  # 65536 bytes
        result = push_data(big_data)
        assert result[0] == OpCode.OP_PUSHDATA4
        size = struct.unpack("<I", result[1:5])[0]
        assert size == 0x10000
        assert result[5:] == big_data

    def test_detect_p2pk_uncompressed(self) -> None:
        """65-byte uncompressed P2PK script detection."""
        # 0x41 = push 65 bytes, then 65 bytes of pubkey, then OP_CHECKSIG
        fake_pubkey = b"\x04" + b"\x01" * 64
        script = bytes([0x41]) + fake_pubkey + bytes([OpCode.OP_CHECKSIG])
        assert detect_script_type(script) == ScriptType.P2PK


# ---------------------------------------------------------------------------
# transaction.py edge cases
# ---------------------------------------------------------------------------


class TestTransactionEdgeCases:
    def test_deserialize_truncated_stream(self) -> None:
        """TxInput.deserialize should raise on truncated prev_tx_id."""
        stream = BytesIO(b"\x00" * 10)
        with pytest.raises(ValueError, match="Unexpected end of stream"):
            TxInput.deserialize(stream)
