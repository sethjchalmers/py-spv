"""Tests for BIP32 HD keys, Base58Check, ECDSA — bsv/keys.py."""

from __future__ import annotations

import pytest

from spv_wallet.bsv.keys import (
    ExtendedKey,
    base58_decode,
    base58_encode,
    base58check_decode,
    base58check_encode,
    compress_public_key,
    decompress_public_key,
    private_key_to_public_key,
    sign_message,
    verify_signature,
    xpub_id,
)
from spv_wallet.utils.crypto import sha256


# ---------------------------------------------------------------------------
# BIP32 Test Vector 1 (from BIP32 spec)
# Seed: 000102030405060708090a0b0c0d0e0f
# ---------------------------------------------------------------------------

_SEED_1 = bytes.fromhex("000102030405060708090a0b0c0d0e0f")

# Expected master keys from BIP32 spec
_XPRV_M = (
    "xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPG"
    "JxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi"
)
_XPUB_M = (
    "xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJo"
    "Cu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8"
)


class TestBase58:
    """Base58 and Base58Check encoding / decoding."""

    def test_encode_empty(self) -> None:
        assert base58_encode(b"") == ""

    def test_encode_decode_roundtrip(self) -> None:
        data = b"\x00\x01\x02\xff"
        encoded = base58_encode(data)
        decoded = base58_decode(encoded)
        assert decoded == data

    def test_leading_zeros(self) -> None:
        """Leading zero bytes map to '1' characters."""
        data = b"\x00\x00\x00\x01"
        encoded = base58_encode(data)
        assert encoded.startswith("111")
        assert base58_decode(encoded) == data

    def test_base58check_roundtrip(self) -> None:
        data = b"\x00" + b"\xab" * 20
        encoded = base58check_encode(data)
        decoded = base58check_decode(encoded)
        assert decoded == data

    def test_base58check_invalid_checksum(self) -> None:
        data = b"\x00" + b"\xab" * 20
        encoded = base58check_encode(data)
        # Corrupt last character
        corrupted = encoded[:-1] + ("1" if encoded[-1] != "1" else "2")
        with pytest.raises(ValueError, match="checksum"):
            base58check_decode(corrupted)

    def test_base58check_too_short(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            base58check_decode("1")


class TestECDSA:
    """ECDSA signing and verification."""

    def test_sign_and_verify(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        msg_hash = sha256(b"test message")
        sig = sign_message(privkey, msg_hash)
        pubkey = private_key_to_public_key(privkey, compressed=True)
        assert verify_signature(pubkey, msg_hash, sig)

    def test_verify_wrong_message(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        msg_hash = sha256(b"test message")
        sig = sign_message(privkey, msg_hash)
        wrong_hash = sha256(b"wrong message")
        pubkey = private_key_to_public_key(privkey)
        assert not verify_signature(pubkey, wrong_hash, sig)

    def test_verify_wrong_key(self) -> None:
        privkey1 = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        privkey2 = bytes.fromhex(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        msg_hash = sha256(b"test")
        sig = sign_message(privkey1, msg_hash)
        wrong_pubkey = private_key_to_public_key(privkey2)
        assert not verify_signature(wrong_pubkey, msg_hash, sig)

    def test_uncompressed_verify(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        msg_hash = sha256(b"test")
        sig = sign_message(privkey, msg_hash)
        pubkey = private_key_to_public_key(privkey, compressed=False)
        assert len(pubkey) == 65
        assert verify_signature(pubkey, msg_hash, sig)


class TestPublicKeyCompression:
    """Compressed / uncompressed public key encoding."""

    def test_compress_from_uncompressed(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        uncompressed = private_key_to_public_key(privkey, compressed=False)
        compressed = compress_public_key(uncompressed)
        expected = private_key_to_public_key(privkey, compressed=True)
        assert compressed == expected

    def test_compress_already_compressed(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        compressed = private_key_to_public_key(privkey, compressed=True)
        assert compress_public_key(compressed) == compressed

    def test_decompress_roundtrip(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        compressed = private_key_to_public_key(privkey)
        decompressed = decompress_public_key(compressed)
        recompressed = compress_public_key(decompressed)
        assert recompressed == compressed

    def test_decompress_invalid_length(self) -> None:
        with pytest.raises(ValueError, match="length"):
            decompress_public_key(b"\x02" + b"\x00" * 20)

    def test_decompress_invalid_prefix(self) -> None:
        with pytest.raises(ValueError, match="prefix"):
            decompress_public_key(b"\x04" + b"\x00" * 32)

    def test_compress_invalid_length(self) -> None:
        with pytest.raises(ValueError, match="length"):
            compress_public_key(b"\x00" * 50)


class TestExtendedKey:
    """BIP32 ExtendedKey operations."""

    def test_from_seed_master(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        assert master.is_private
        assert master.depth == 0
        assert master.parent_fingerprint == b"\x00\x00\x00\x00"
        assert master.child_index == 0

    def test_master_xprv_matches_spec(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        assert master.to_string() == _XPRV_M

    def test_master_xpub_matches_spec(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        pub = master.neuter()
        assert pub.to_string() == _XPUB_M
        assert not pub.is_private

    def test_roundtrip_xprv(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        s = master.to_string()
        restored = ExtendedKey.from_string(s)
        assert restored.key == master.key
        assert restored.chain_code == master.chain_code
        assert restored.is_private

    def test_roundtrip_xpub(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        pub = master.neuter()
        s = pub.to_string()
        restored = ExtendedKey.from_string(s)
        assert restored.key == pub.key
        assert not restored.is_private

    def test_derive_child_normal(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        child = master.derive_child(0)
        assert child.depth == 1
        assert child.child_index == 0
        assert child.is_private

    def test_derive_child_hardened(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        child = master.derive_child(0x80000000)
        assert child.depth == 1
        assert child.is_private

    def test_hardened_derivation_from_public_key_raises(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        pub = master.neuter()
        with pytest.raises(ValueError, match="hardened"):
            pub.derive_child(0x80000000)

    def test_derive_path(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        # m/0'/1/2'/2/1000000000  (BIP32 test vector 1 chain)
        child = master.derive_path("m/0'/1/2'/2/1000000000")
        assert child.depth == 5

    def test_derive_path_h_notation(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        child_apostrophe = master.derive_path("m/0'/1")
        child_h = master.derive_path("m/0h/1")
        assert child_apostrophe.key == child_h.key

    def test_public_key_derivation_matches_private(self) -> None:
        """Public child derivation should produce same pubkey as private child neuter."""
        master = ExtendedKey.from_seed(_SEED_1)
        # Derive m/0 via private then neuter
        priv_child = master.derive_child(0)
        pub_from_priv = priv_child.neuter()

        # Derive m/0 via public derivation
        master_pub = master.neuter()
        pub_child = master_pub.derive_child(0)

        assert pub_from_priv.key == pub_child.key
        assert pub_from_priv.chain_code == pub_child.chain_code

    def test_neuter_idempotent(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        pub = master.neuter()
        pub2 = pub.neuter()
        assert pub.key == pub2.key

    def test_public_key_from_private(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        pubkey = master.public_key()
        assert len(pubkey) == 33
        assert pubkey[0] in (0x02, 0x03)

    def test_from_string_invalid_length(self) -> None:
        with pytest.raises(ValueError, match="length"):
            ExtendedKey.from_string(base58check_encode(b"\x00" * 50))

    def test_seed_too_short(self) -> None:
        with pytest.raises(ValueError, match="16"):
            ExtendedKey.from_seed(b"\x00" * 10)

    def test_seed_too_long(self) -> None:
        with pytest.raises(ValueError, match="16"):
            ExtendedKey.from_seed(b"\x00" * 100)

    def test_fingerprint(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        fp = master.fingerprint()
        assert len(fp) == 4

    def test_bip32_vector1_chain(self) -> None:
        """BIP32 test vector 1 — full chain m/0'/1/2'/2/1000000000."""
        master = ExtendedKey.from_seed(_SEED_1)
        # m/0'
        child = master.derive_child(0x80000000)
        expected_xpub = (
            "xpub68Gmy5EdvgibQVfPdqkBBCHxA5htiqg55crXYuXoQRKfDBFA1WEjWg"
            "P6LHhwBZeNK1VTsfTFUHCdrfp1bgwQ9xv5ski8PX9rL2dZXvgGDnw"
        )
        assert child.neuter().to_string() == expected_xpub


class TestXPubId:
    """xPub → xPubID hashing."""

    def test_xpub_id_deterministic(self) -> None:
        result1 = xpub_id(_XPUB_M)
        result2 = xpub_id(_XPUB_M)
        assert result1 == result2
        assert len(result1) == 64  # 32 bytes hex

    def test_xpub_id_is_sha256(self) -> None:
        expected = sha256(_XPUB_M.encode("utf-8")).hex()
        assert xpub_id(_XPUB_M) == expected

    def test_different_xpubs_different_ids(self) -> None:
        master = ExtendedKey.from_seed(_SEED_1)
        child = master.derive_child(0)
        id1 = xpub_id(master.neuter().to_string())
        id2 = xpub_id(child.neuter().to_string())
        assert id1 != id2
