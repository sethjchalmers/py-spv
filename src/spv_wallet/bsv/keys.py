"""BIP32 HD key derivation — xPub / xPriv, child key derivation, key ID hashing.

Implements BIP32 hierarchical deterministic wallets for BSV:
- Extended key serialization / deserialization (xpub/xprv, Base58Check)
- Child key derivation (hardened & normal)
- xPub → xPubID hashing (SHA-256 of the serialized xPub)
- ECDSA signing and verification on secp256k1
- Compressed / uncompressed public key encoding
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass
from typing import Self

from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.ellipticcurve import INFINITY

from spv_wallet.utils.crypto import hash160, sha256, sha256d

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CURVE = SECP256k1
_CURVE_ORDER = _CURVE.order
_CURVE_GEN = _CURVE.generator

# BIP32 version bytes (mainnet)
_XPUB_VERSION = b"\x04\x88\xb2\x1e"  # xpub
_XPRV_VERSION = b"\x04\x88\xad\xe4"  # xprv

# BIP32 version bytes (testnet)
_TPUB_VERSION = b"\x04\x35\x87\xcf"  # tpub
_TPRV_VERSION = b"\x04\x35\x83\x94"  # tprv

# BIP32 seed HMAC key
_MASTER_HMAC_KEY = b"Bitcoin seed"


# ---------------------------------------------------------------------------
# Base58Check encoding / decoding
# ---------------------------------------------------------------------------

_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_encode(payload: bytes) -> str:
    """Encode raw bytes to Base58 (no checksum)."""
    n = int.from_bytes(payload, "big")
    result: list[int] = []
    while n > 0:
        n, remainder = divmod(n, 58)
        result.append(_B58_ALPHABET[remainder])
    # Preserve leading zero bytes
    for byte in payload:
        if byte == 0:
            result.append(_B58_ALPHABET[0])
        else:
            break
    return bytes(reversed(result)).decode("ascii")


def base58_decode(s: str) -> bytes:
    """Decode Base58 string to raw bytes (no checksum)."""
    n = 0
    for char in s:
        n = n * 58 + _B58_ALPHABET.index(char.encode("ascii"))
    # Calculate required byte length
    result = n.to_bytes((n.bit_length() + 7) // 8, "big") if n > 0 else b""
    # Preserve leading '1' chars as 0x00 bytes
    pad_count = 0
    for char in s:
        if char == "1":
            pad_count += 1
        else:
            break
    return b"\x00" * pad_count + result


def base58check_encode(payload: bytes) -> str:
    """Encode bytes with a 4-byte SHA256d checksum (Base58Check)."""
    checksum = sha256d(payload)[:4]
    return base58_encode(payload + checksum)


def base58check_decode(s: str) -> bytes:
    """Decode a Base58Check string, verifying the checksum.

    Raises:
        ValueError: If the checksum is invalid.
    """
    raw = base58_decode(s)
    if len(raw) < 4:
        msg = "Base58Check string too short"
        raise ValueError(msg)
    payload, checksum = raw[:-4], raw[-4:]
    expected = sha256d(payload)[:4]
    if checksum != expected:
        msg = "Base58Check checksum mismatch"
        raise ValueError(msg)
    return payload


# ---------------------------------------------------------------------------
# ECDSA helpers
# ---------------------------------------------------------------------------


def private_key_to_public_key(privkey_bytes: bytes, *, compressed: bool = True) -> bytes:
    """Derive the public key from a 32-byte private key.

    Args:
        privkey_bytes: 32-byte big-endian scalar.
        compressed: If True, return the 33-byte SEC compressed encoding.

    Returns:
        The public key bytes (33 compressed or 65 uncompressed).
    """
    sk = SigningKey.from_string(privkey_bytes, curve=_CURVE)
    vk = sk.get_verifying_key()
    if compressed:
        return compress_public_key(vk.to_string())
    return b"\x04" + vk.to_string()


def compress_public_key(raw_pubkey: bytes) -> bytes:
    """Compress a 64-byte (or 65-byte with 0x04 prefix) raw public key to 33 bytes."""
    if len(raw_pubkey) == 65 and raw_pubkey[0] == 0x04:
        raw_pubkey = raw_pubkey[1:]
    if len(raw_pubkey) != 64:
        if len(raw_pubkey) == 33 and raw_pubkey[0] in (0x02, 0x03):
            return raw_pubkey  # Already compressed
        msg = f"Invalid raw public key length: {len(raw_pubkey)}"
        raise ValueError(msg)
    x = int.from_bytes(raw_pubkey[:32], "big")
    y = int.from_bytes(raw_pubkey[32:], "big")
    prefix = b"\x02" if y % 2 == 0 else b"\x03"
    return prefix + x.to_bytes(32, "big")


def decompress_public_key(compressed: bytes) -> bytes:
    """Decompress a 33-byte compressed public key to 65-byte uncompressed."""
    if len(compressed) != 33:
        msg = f"Invalid compressed key length: {len(compressed)}"
        raise ValueError(msg)
    prefix = compressed[0]
    if prefix not in (0x02, 0x03):
        msg = f"Invalid compressed key prefix: {prefix:#x}"
        raise ValueError(msg)
    x = int.from_bytes(compressed[1:], "big")
    p = _CURVE.curve.p()
    # y^2 = x^3 + 7  (mod p)  for secp256k1
    y_sq = (pow(x, 3, p) + 7) % p
    y = pow(y_sq, (p + 1) // 4, p)
    if (y % 2 == 0) != (prefix == 0x02):
        y = p - y
    return b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big")


def sign_message(privkey_bytes: bytes, message_hash: bytes) -> bytes:
    """Sign a 32-byte hash with the private key (DER-encoded signature)."""
    sk = SigningKey.from_string(privkey_bytes, curve=_CURVE)
    return sk.sign_digest(message_hash, sigencode=_der_encode)


def verify_signature(pubkey_bytes: bytes, message_hash: bytes, signature: bytes) -> bool:
    """Verify a DER-encoded signature against a public key and message hash."""
    if len(pubkey_bytes) == 33:
        uncompressed = decompress_public_key(pubkey_bytes)
        raw_key = uncompressed[1:]
    elif len(pubkey_bytes) == 65:
        raw_key = pubkey_bytes[1:]
    else:
        raw_key = pubkey_bytes
    vk = VerifyingKey.from_string(raw_key, curve=_CURVE)
    try:
        return vk.verify_digest(signature, message_hash, sigdecode=_der_decode)
    except Exception:
        return False


def _der_encode(r: int, s: int, order: int) -> bytes:
    """Encode r, s as DER signature."""
    rb = _int_to_der_bytes(r)
    sb = _int_to_der_bytes(s)
    return b"\x30" + bytes([len(rb) + len(sb)]) + rb + sb


def _der_decode(signature: bytes, order: int) -> tuple[int, int]:
    """Decode DER signature to (r, s)."""
    if signature[0] != 0x30:
        msg = "Invalid DER signature"
        raise ValueError(msg)
    idx = 2  # skip 0x30 and length byte
    if signature[idx] != 0x02:
        msg = "Invalid DER signature (r marker)"
        raise ValueError(msg)
    idx += 1
    r_len = signature[idx]
    idx += 1
    r = int.from_bytes(signature[idx : idx + r_len], "big")
    idx += r_len
    if signature[idx] != 0x02:
        msg = "Invalid DER signature (s marker)"
        raise ValueError(msg)
    idx += 1
    s_len = signature[idx]
    idx += 1
    s = int.from_bytes(signature[idx : idx + s_len], "big")
    return r, s


def _int_to_der_bytes(n: int) -> bytes:
    """Encode an integer as a DER INTEGER TLV."""
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    if b[0] & 0x80:
        b = b"\x00" + b
    return b"\x02" + bytes([len(b)]) + b


# ---------------------------------------------------------------------------
# BIP32 Extended Key
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtendedKey:
    """A BIP32 extended key (public or private).

    Attributes:
        key: 33-byte compressed pubkey *or* 32-byte privkey scalar.
        chain_code: 32-byte chain code.
        depth: Derivation depth (0 for master).
        parent_fingerprint: First 4 bytes of parent's Hash160(pubkey).
        child_index: Index used in derivation.
        is_private: True if this key holds the private scalar.
        testnet: True if this is a testnet key (tpub/tprv).
    """

    key: bytes
    chain_code: bytes
    depth: int
    parent_fingerprint: bytes
    child_index: int
    is_private: bool
    testnet: bool = False

    # -- Serialization -----------------------------------------------------

    def serialize(self) -> bytes:
        """Serialize to the 78-byte BIP32 format."""
        if self.is_private:
            version = _TPRV_VERSION if self.testnet else _XPRV_VERSION
        else:
            version = _TPUB_VERSION if self.testnet else _XPUB_VERSION
        data = version
        data += struct.pack("B", self.depth)
        data += self.parent_fingerprint
        data += struct.pack(">I", self.child_index)
        data += self.chain_code
        if self.is_private:
            data += b"\x00" + self.key  # 33 bytes with leading 0x00
        else:
            data += self.key  # 33 bytes compressed pubkey
        return data

    def to_string(self) -> str:
        """Encode as Base58Check xpub/xprv string."""
        return base58check_encode(self.serialize())

    @classmethod
    def from_string(cls, s: str) -> Self:
        """Decode a Base58Check xpub/xprv string."""
        data = base58check_decode(s)
        if len(data) != 78:
            msg = f"Invalid extended key length: {len(data)}"
            raise ValueError(msg)
        version = data[:4]
        if version == _XPRV_VERSION:
            is_private = True
            testnet = False
        elif version == _XPUB_VERSION:
            is_private = False
            testnet = False
        elif version == _TPRV_VERSION:
            is_private = True
            testnet = True
        elif version == _TPUB_VERSION:
            is_private = False
            testnet = True
        else:
            msg = f"Unknown version bytes: {version.hex()}"
            raise ValueError(msg)
        depth = data[4]
        parent_fp = data[5:9]
        child_index = struct.unpack(">I", data[9:13])[0]
        chain_code = data[13:45]
        key = data[46:78] if is_private else data[45:78]
        return cls(
            key=key,
            chain_code=chain_code,
            depth=depth,
            parent_fingerprint=parent_fp,
            child_index=child_index,
            is_private=is_private,
            testnet=testnet,
        )

    # -- Derivation --------------------------------------------------------

    def public_key(self) -> bytes:
        """Return the 33-byte compressed public key."""
        if self.is_private:
            return private_key_to_public_key(self.key, compressed=True)
        return self.key

    def fingerprint(self) -> bytes:
        """First 4 bytes of Hash160(compressed pubkey)."""
        return hash160(self.public_key())[:4]

    def neuter(self) -> ExtendedKey:
        """Convert private extended key to its public counterpart."""
        if not self.is_private:
            return self
        return ExtendedKey(
            key=self.public_key(),
            chain_code=self.chain_code,
            depth=self.depth,
            parent_fingerprint=self.parent_fingerprint,
            child_index=self.child_index,
            is_private=False,
            testnet=self.testnet,
        )

    def derive_child(self, index: int) -> ExtendedKey:
        """Derive a child key at the given index.

        Use ``index >= 0x80000000`` for hardened derivation (requires private key).

        Raises:
            ValueError: If hardened derivation is requested on a public key,
                        or if the derived key is invalid.
        """
        hardened = index >= 0x80000000
        if hardened and not self.is_private:
            msg = "Cannot derive hardened child from public key"
            raise ValueError(msg)

        if hardened:
            # Data = 0x00 || private_key || index
            data = b"\x00" + self.key + struct.pack(">I", index)
        else:
            # Data = compressed_pubkey || index
            data = self.public_key() + struct.pack(">I", index)

        hmac_result = hmac.new(self.chain_code, data, hashlib.sha512).digest()
        il, ir = hmac_result[:32], hmac_result[32:]

        il_int = int.from_bytes(il, "big")
        if il_int >= _CURVE_ORDER:
            msg = "Derived key is invalid (il >= curve order)"
            raise ValueError(msg)

        fp = self.fingerprint()

        if self.is_private:
            key_int = (il_int + int.from_bytes(self.key, "big")) % _CURVE_ORDER
            if key_int == 0:
                msg = "Derived key is invalid (key == 0)"
                raise ValueError(msg)
            child_key = key_int.to_bytes(32, "big")
            return ExtendedKey(
                key=child_key,
                chain_code=ir,
                depth=self.depth + 1,
                parent_fingerprint=fp,
                child_index=index,
                is_private=True,
                testnet=self.testnet,
            )
        else:
            # Public key derivation: point(il) + parent_pubkey
            parent_point = _pubkey_to_point(self.key)
            il_point = _CURVE_GEN * il_int
            child_point = parent_point + il_point
            if child_point == INFINITY:
                msg = "Derived key is invalid (point at infinity)"
                raise ValueError(msg)
            child_key = _point_to_compressed(child_point)
            return ExtendedKey(
                key=child_key,
                chain_code=ir,
                depth=self.depth + 1,
                parent_fingerprint=fp,
                child_index=index,
                is_private=False,
                testnet=self.testnet,
            )

    def derive_path(self, path: str) -> ExtendedKey:
        """Derive using a BIP32 path string like ``m/44'/0'/0'/0/0``.

        Apostrophe (') or h indicates hardened derivation.
        """
        parts = path.strip().split("/")
        key = self
        for part in parts:
            if part in ("m", "M", ""):
                continue
            hardened = part.endswith(("'", "h", "H"))
            idx_str = part.rstrip("'hH")
            idx = int(idx_str)
            if hardened:
                idx += 0x80000000
            key = key.derive_child(idx)
        return key

    @classmethod
    def from_seed(cls, seed: bytes, *, testnet: bool = False) -> ExtendedKey:
        """Create a master private extended key from a BIP32 seed.

        Args:
            seed: 16-64 byte seed (typically 32 from BIP39 mnemonic).
            testnet: If True, create a testnet key (tprv prefix).

        Raises:
            ValueError: If seed length is out of range.
        """
        if not 16 <= len(seed) <= 64:
            msg = f"Seed must be 16-64 bytes, got {len(seed)}"
            raise ValueError(msg)
        hmac_result = hmac.new(_MASTER_HMAC_KEY, seed, hashlib.sha512).digest()
        il, ir = hmac_result[:32], hmac_result[32:]
        il_int = int.from_bytes(il, "big")
        if il_int == 0 or il_int >= _CURVE_ORDER:
            msg = "Invalid seed (derived key out of range)"
            raise ValueError(msg)
        return cls(
            key=il,
            chain_code=ir,
            depth=0,
            parent_fingerprint=b"\x00\x00\x00\x00",
            child_index=0,
            is_private=True,
            testnet=testnet,
        )


# ---------------------------------------------------------------------------
# xPub ID hashing (SHA-256 of serialized xPub key)
# ---------------------------------------------------------------------------


def xpub_id(xpub_str: str) -> str:
    """Compute the xPubID — SHA-256 hex digest of the serialized xPub string.

    This matches the Go ``utils.Hash(xPub)`` function used to identify xPubs.
    """
    return sha256(xpub_str.encode("utf-8")).hex()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _pubkey_to_point(compressed: bytes):  # type: ignore[no-untyped-def]
    """Decode a 33-byte compressed public key to an elliptic curve point."""
    uncompressed = decompress_public_key(compressed)
    x = int.from_bytes(uncompressed[1:33], "big")
    y = int.from_bytes(uncompressed[33:65], "big")
    from ecdsa.ellipticcurve import Point

    return Point(_CURVE.curve, x, y)


def _point_to_compressed(point) -> bytes:  # type: ignore[no-untyped-def]
    """Encode an elliptic curve point as a 33-byte compressed public key."""
    x_bytes = point.x().to_bytes(32, "big")
    prefix = b"\x02" if point.y() % 2 == 0 else b"\x03"
    return prefix + x_bytes
