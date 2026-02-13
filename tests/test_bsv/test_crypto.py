"""Tests for crypto utility functions."""

from __future__ import annotations

from spv_wallet.utils.crypto import hash160, ripemd160, sha256, sha256d


def test_sha256():
    """SHA-256 of empty string should produce the well-known hash."""
    result = sha256(b"")
    assert result.hex() == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256d():
    """Double SHA-256 of empty string."""
    result = sha256d(b"")
    # SHA256(SHA256("")) is a known constant
    expected = sha256(sha256(b""))
    assert result == expected


def test_ripemd160():
    """RIPEMD-160 of empty string."""
    result = ripemd160(b"")
    assert result.hex() == "9c1185a5c5e9fc54612808977ee8f548b2258d31"


def test_hash160():
    """Hash160 should be RIPEMD160(SHA256(data))."""
    data = b"hello"
    expected = ripemd160(sha256(data))
    assert hash160(data) == expected
