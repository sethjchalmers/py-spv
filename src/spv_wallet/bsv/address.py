"""Address encoding — Base58Check, address utilities.

BSV address operations:
- P2PKH address generation from public keys
- Address validation and type detection
- WIF (Wallet Import Format) encoding/decoding
"""

from __future__ import annotations

from spv_wallet.bsv.keys import base58check_decode, base58check_encode
from spv_wallet.utils.crypto import hash160

# Network version bytes
_MAINNET_PUBKEY_HASH = b"\x00"  # 1...
_TESTNET_PUBKEY_HASH = b"\x6f"  # m... or n...
_MAINNET_WIF = b"\x80"
_TESTNET_WIF = b"\xef"


def pubkey_to_address(pubkey: bytes, *, testnet: bool = False) -> str:
    """Generate a P2PKH address from a compressed/uncompressed public key.

    Args:
        pubkey: 33-byte compressed or 65-byte uncompressed public key.
        testnet: If True, use testnet version byte.

    Returns:
        Base58Check-encoded P2PKH address.
    """
    h = hash160(pubkey)
    version = _TESTNET_PUBKEY_HASH if testnet else _MAINNET_PUBKEY_HASH
    return base58check_encode(version + h)


def address_to_pubkey_hash(address: str) -> bytes:
    """Extract the 20-byte public key hash from a P2PKH address.

    Args:
        address: Base58Check-encoded P2PKH address.

    Returns:
        The 20-byte RIPEMD160(SHA256(pubkey)) hash.

    Raises:
        ValueError: If the address is invalid or not P2PKH.
    """
    payload = base58check_decode(address)
    if len(payload) != 21:
        msg = f"Invalid address payload length: {len(payload)}"
        raise ValueError(msg)
    return payload[1:]


def validate_address(address: str) -> bool:
    """Check if an address is a valid Base58Check-encoded P2PKH address."""
    try:
        payload = base58check_decode(address)
        return len(payload) == 21 and payload[0] in (0x00, 0x6F)
    except ValueError:
        return False


def privkey_to_wif(privkey: bytes, *, compressed: bool = True, testnet: bool = False) -> str:
    """Encode a 32-byte private key as WIF (Wallet Import Format).

    Args:
        privkey: 32-byte private key scalar.
        compressed: Append 0x01 flag indicating compressed public key.
        testnet: Use testnet version byte.

    Returns:
        WIF-encoded string.
    """
    version = _TESTNET_WIF if testnet else _MAINNET_WIF
    payload = version + privkey
    if compressed:
        payload += b"\x01"
    return base58check_encode(payload)


def wif_to_privkey(wif: str) -> tuple[bytes, bool, bool]:
    """Decode a WIF string to a private key.

    Returns:
        Tuple of (privkey_bytes, compressed, testnet).
    """
    payload = base58check_decode(wif)
    if len(payload) not in (33, 34):
        msg = f"Invalid WIF payload length: {len(payload)}"
        raise ValueError(msg)
    version = payload[0:1]
    testnet = version == _TESTNET_WIF
    if len(payload) == 34 and payload[-1] == 0x01:
        return payload[1:33], True, testnet
    return payload[1:33], False, testnet
