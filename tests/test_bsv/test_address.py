"""Tests for address utilities — bsv/address.py."""

from __future__ import annotations

import pytest

from spv_wallet.bsv.address import (
    address_to_pubkey_hash,
    privkey_to_wif,
    pubkey_to_address,
    validate_address,
    wif_to_privkey,
)
from spv_wallet.bsv.keys import ExtendedKey, private_key_to_public_key
from spv_wallet.utils.crypto import hash160

_SEED = bytes.fromhex("000102030405060708090a0b0c0d0e0f")


class TestPubkeyToAddress:
    """P2PKH address generation from public keys."""

    def test_mainnet_address(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pubkey = master.public_key()
        address = pubkey_to_address(pubkey)
        # Mainnet addresses start with '1'
        assert address.startswith("1")
        assert validate_address(address)

    def test_testnet_address(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pubkey = master.public_key()
        address = pubkey_to_address(pubkey, testnet=True)
        # Testnet addresses start with 'm' or 'n'
        assert address[0] in ("m", "n")
        assert validate_address(address)

    def test_address_from_known_privkey(self) -> None:
        """Known private key → public key → address."""
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        pubkey = private_key_to_public_key(privkey, compressed=True)
        address = pubkey_to_address(pubkey)
        assert address.startswith("1")
        assert len(address) >= 25

    def test_uncompressed_pubkey_address(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        pubkey = private_key_to_public_key(privkey, compressed=False)
        address = pubkey_to_address(pubkey)
        assert address.startswith("1")


class TestAddressToPubkeyHash:
    """Extract pubkey hash from address."""

    def test_roundtrip(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pubkey = master.public_key()
        expected_hash = hash160(pubkey)
        address = pubkey_to_address(pubkey)
        extracted = address_to_pubkey_hash(address)
        assert extracted == expected_hash

    def test_invalid_address(self) -> None:
        with pytest.raises(ValueError):
            address_to_pubkey_hash("not_a_valid_address_but_lets_try")


class TestValidateAddress:
    """Address validation."""

    def test_valid_mainnet(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pubkey = master.public_key()
        address = pubkey_to_address(pubkey)
        assert validate_address(address)

    def test_valid_testnet(self) -> None:
        master = ExtendedKey.from_seed(_SEED)
        pubkey = master.public_key()
        address = pubkey_to_address(pubkey, testnet=True)
        assert validate_address(address)

    def test_invalid_string(self) -> None:
        assert not validate_address("notavalidaddress")

    def test_empty_string(self) -> None:
        assert not validate_address("")


class TestWIF:
    """Wallet Import Format encoding/decoding."""

    def test_wif_compressed_mainnet(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        wif = privkey_to_wif(privkey, compressed=True, testnet=False)
        assert wif.startswith(("5", "K", "L"))
        decoded, compressed, testnet = wif_to_privkey(wif)
        assert decoded == privkey
        assert compressed is True
        assert testnet is False

    def test_wif_uncompressed_mainnet(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        wif = privkey_to_wif(privkey, compressed=False, testnet=False)
        decoded, compressed, testnet = wif_to_privkey(wif)
        assert decoded == privkey
        assert compressed is False
        assert testnet is False

    def test_wif_compressed_testnet(self) -> None:
        privkey = bytes.fromhex(
            "e8f32e723decf4051aefac8e2c93c9c5b214313817cdb01a1494b917c8436b35"
        )
        wif = privkey_to_wif(privkey, compressed=True, testnet=True)
        decoded, compressed, testnet = wif_to_privkey(wif)
        assert decoded == privkey
        assert compressed is True
        assert testnet is True

    def test_wif_invalid(self) -> None:
        with pytest.raises(ValueError):
            wif_to_privkey("invalidwif")
