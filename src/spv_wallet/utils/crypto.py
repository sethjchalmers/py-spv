"""Cryptographic helpers — hashing, HMAC, encryption."""

from __future__ import annotations

import hashlib


def sha256(data: bytes) -> bytes:
    """Single SHA-256 hash."""
    return hashlib.sha256(data).digest()


def sha256d(data: bytes) -> bytes:
    """Double SHA-256 hash (SHA256(SHA256(data)))."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def ripemd160(data: bytes) -> bytes:
    """RIPEMD-160 hash."""
    h = hashlib.new("ripemd160")
    h.update(data)
    return h.digest()


def hash160(data: bytes) -> bytes:
    """RIPEMD-160(SHA-256(data)) — standard Bitcoin Hash160."""
    return ripemd160(sha256(data))
