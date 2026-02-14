"""Tests for Merkle path verification — BRC-71 parsing, root computation."""

from __future__ import annotations

import struct

import pytest

from spv_wallet.bsv.merkle import (
    MerklePath,
    MerklePathNode,
    compute_merkle_root,
    verify_merkle_path,
)
from spv_wallet.bsv.transaction import encode_varint
from spv_wallet.utils.crypto import sha256d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_brc71_hex(block_height: int, levels: list[list[tuple[int, int, bytes | None]]]) -> str:
    """Build a BRC-71 compact Merkle path hex string.

    Args:
        block_height: Block height.
        levels: List of levels, each a list of (offset, flags, hash_32bytes_or_None).
                flags: 0x01=duplicate, 0x02=txid. If duplicate, hash can be None.

    Returns:
        Hex-encoded BRC-71 path.
    """
    data = struct.pack("<I", block_height)
    data += struct.pack("<B", len(levels))

    for level_nodes in levels:
        data += encode_varint(len(level_nodes))
        for offset, flags, hash_bytes in level_nodes:
            data += encode_varint(offset)
            data += struct.pack("<B", flags)
            if not (flags & 0x01):  # Not duplicate → include hash
                assert hash_bytes is not None and len(hash_bytes) == 32
                data += hash_bytes  # stored in internal byte order

    return data.hex()


# ---------------------------------------------------------------------------
# MerklePathNode
# ---------------------------------------------------------------------------


class TestMerklePathNode:
    def test_defaults(self):
        node = MerklePathNode(offset=0)
        assert node.offset == 0
        assert node.hash == ""
        assert node.txid is False
        assert node.duplicate is False

    def test_with_values(self):
        node = MerklePathNode(offset=3, hash="ab" * 32, txid=True)
        assert node.offset == 3
        assert node.txid is True


# ---------------------------------------------------------------------------
# MerklePath.from_hex — BRC-71 parsing
# ---------------------------------------------------------------------------


class TestMerklePathFromHex:
    def test_simple_two_tx_block(self):
        """Block with 2 txs → 1 level, 2 nodes."""
        tx_a = sha256d(b"tx_a")  # internal byte order
        tx_b = sha256d(b"tx_b")

        hex_str = _make_brc71_hex(
            block_height=800000,
            levels=[
                [
                    (0, 0x02, tx_a[::-1]),  # txid-flagged (stored reversed in binary)
                    (1, 0x00, tx_b[::-1]),  # sibling
                ],
            ],
        )
        mp = MerklePath.from_hex(hex_str)
        assert mp.block_height == 800000
        assert len(mp.path) == 1
        assert len(mp.path[0]) == 2
        assert mp.path[0][0].txid is True
        assert mp.path[0][0].offset == 0

    def test_duplicate_node(self):
        """Odd-count level → duplicate flag."""
        tx_a = sha256d(b"tx_a")

        hex_str = _make_brc71_hex(
            block_height=100,
            levels=[
                [
                    (0, 0x02, tx_a[::-1]),  # txid
                    (1, 0x01, None),        # duplicate
                ],
            ],
        )
        mp = MerklePath.from_hex(hex_str)
        assert mp.path[0][1].duplicate is True
        assert mp.path[0][1].hash == ""

    def test_multiple_levels(self):
        """3 levels → tree height of 3."""
        h = sha256d(b"data")

        hex_str = _make_brc71_hex(
            block_height=500,
            levels=[
                [(0, 0x02, h[::-1]), (1, 0x00, h[::-1])],
                [(0, 0x00, h[::-1]), (1, 0x00, h[::-1])],
                [(0, 0x00, h[::-1]), (1, 0x00, h[::-1])],
            ],
        )
        mp = MerklePath.from_hex(hex_str)
        assert len(mp.path) == 3


# ---------------------------------------------------------------------------
# compute_root
# ---------------------------------------------------------------------------


class TestComputeRoot:
    def test_two_tx_root(self):
        """Root of a block with 2 transactions."""
        # Build known hashes
        tx_a_hash = sha256d(b"tx_a")  # internal byte order
        tx_b_hash = sha256d(b"tx_b")

        expected_root = sha256d(tx_a_hash + tx_b_hash)
        expected_root_display = expected_root[::-1].hex()

        # Build Merkle path for tx_a: sibling is tx_b at offset 1
        mp = MerklePath(
            block_height=1000,
            path=[
                [
                    MerklePathNode(offset=0, hash=tx_a_hash[::-1].hex(), txid=True),
                    MerklePathNode(offset=1, hash=tx_b_hash[::-1].hex()),
                ],
            ],
        )

        root = mp.compute_root()
        assert root == expected_root_display

    def test_compute_root_with_explicit_txid(self):
        """Provide txid explicitly."""
        tx_a_hash = sha256d(b"tx_a")
        tx_b_hash = sha256d(b"tx_b")
        expected_root = sha256d(tx_a_hash + tx_b_hash)

        mp = MerklePath(
            block_height=1000,
            path=[
                [
                    MerklePathNode(offset=0, hash=tx_a_hash[::-1].hex(), txid=True),
                    MerklePathNode(offset=1, hash=tx_b_hash[::-1].hex()),
                ],
            ],
        )

        root = mp.compute_root(txid=tx_a_hash[::-1].hex())
        assert root == expected_root[::-1].hex()

    def test_compute_root_right_side(self):
        """Target tx is on the right side (offset 1)."""
        tx_a_hash = sha256d(b"tx_a")
        tx_b_hash = sha256d(b"tx_b")
        expected_root = sha256d(tx_a_hash + tx_b_hash)

        mp = MerklePath(
            block_height=1000,
            path=[
                [
                    MerklePathNode(offset=0, hash=tx_a_hash[::-1].hex()),
                    MerklePathNode(offset=1, hash=tx_b_hash[::-1].hex(), txid=True),
                ],
            ],
        )

        root = mp.compute_root()
        assert root == expected_root[::-1].hex()

    def test_compute_root_duplicate(self):
        """Single tx in block → duplicate sibling."""
        tx_hash = sha256d(b"only_tx")
        expected_root = sha256d(tx_hash + tx_hash)

        mp = MerklePath(
            block_height=500,
            path=[
                [
                    MerklePathNode(offset=0, hash=tx_hash[::-1].hex(), txid=True),
                    MerklePathNode(offset=1, duplicate=True),
                ],
            ],
        )

        root = mp.compute_root()
        assert root == expected_root[::-1].hex()

    def test_empty_path_raises(self):
        mp = MerklePath(block_height=0, path=[])
        with pytest.raises(ValueError, match="Empty"):
            mp.compute_root()

    def test_no_txid_node_raises(self):
        mp = MerklePath(
            block_height=0,
            path=[
                [MerklePathNode(offset=0, hash="ab" * 32)],  # No txid flag
            ],
        )
        with pytest.raises(ValueError, match="No txid"):
            mp.compute_root()


# ---------------------------------------------------------------------------
# verify_merkle_path (standalone function)
# ---------------------------------------------------------------------------


class TestVerifyMerklePath:
    def test_valid_verification(self):
        tx_a_hash = sha256d(b"tx_a")
        tx_b_hash = sha256d(b"tx_b")
        expected_root = sha256d(tx_a_hash + tx_b_hash)[::-1].hex()

        mp = MerklePath(
            block_height=1000,
            path=[
                [
                    MerklePathNode(offset=0, hash=tx_a_hash[::-1].hex(), txid=True),
                    MerklePathNode(offset=1, hash=tx_b_hash[::-1].hex()),
                ],
            ],
        )

        assert verify_merkle_path(tx_a_hash[::-1].hex(), mp, expected_root) is True

    def test_invalid_root(self):
        tx_hash = sha256d(b"tx")
        mp = MerklePath(
            block_height=1,
            path=[
                [
                    MerklePathNode(offset=0, hash=tx_hash[::-1].hex(), txid=True),
                    MerklePathNode(offset=1, duplicate=True),
                ],
            ],
        )
        assert verify_merkle_path(tx_hash[::-1].hex(), mp, "ff" * 32) is False


# ---------------------------------------------------------------------------
# compute_merkle_root (from tx hash list)
# ---------------------------------------------------------------------------


class TestComputeMerkleRoot:
    def test_single_hash(self):
        h = sha256d(b"single")
        assert compute_merkle_root([h]) == h

    def test_two_hashes(self):
        h1 = sha256d(b"h1")
        h2 = sha256d(b"h2")
        expected = sha256d(h1 + h2)
        assert compute_merkle_root([h1, h2]) == expected

    def test_three_hashes_odd_duplication(self):
        h1, h2, h3 = sha256d(b"1"), sha256d(b"2"), sha256d(b"3")
        # Level 0: combine (h1,h2) and (h3,h3)
        l0a = sha256d(h1 + h2)
        l0b = sha256d(h3 + h3)
        expected = sha256d(l0a + l0b)
        assert compute_merkle_root([h1, h2, h3]) == expected

    def test_four_hashes(self):
        hashes = [sha256d(bytes([i])) for i in range(4)]
        l0a = sha256d(hashes[0] + hashes[1])
        l0b = sha256d(hashes[2] + hashes[3])
        expected = sha256d(l0a + l0b)
        assert compute_merkle_root(hashes) == expected

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_merkle_root([])
