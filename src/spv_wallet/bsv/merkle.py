"""Merkle path verification — proof-of-inclusion against block headers.

Implements BRC-71 Merkle path verification for SPV:
- Verify that a transaction is included in a block given a Merkle path
- Parse Merkle path from the compact BRC-71 string format
- Compute Merkle root from a transaction hash and its path
"""

from __future__ import annotations

from dataclasses import dataclass, field

from spv_wallet.utils.crypto import sha256d


# ---------------------------------------------------------------------------
# Merkle path data structures
# ---------------------------------------------------------------------------


@dataclass
class MerklePathNode:
    """A single node in a Merkle proof path.

    Attributes:
        offset: The index of the node at this level (0-based).
        hash: The 32-byte hash of the sibling node (hex string).
        txid: Whether this node is the target txid (True) or a sibling hash.
        duplicate: Whether this node is a duplicate (odd-node duplication).
    """

    offset: int
    hash: str = ""
    txid: bool = False
    duplicate: bool = False


@dataclass
class MerklePath:
    """A BRC-71 Merkle path — a list of levels from leaf to root.

    Each level is a list of MerklePathNodes representing the hashes
    at that tree depth. The leaf level (index 0) contains the target
    transaction and its sibling.

    Attributes:
        block_height: The block height this path belongs to.
        path: List of levels (each level is a list of nodes).
    """

    block_height: int = 0
    path: list[list[MerklePathNode]] = field(default_factory=list)

    @classmethod
    def from_hex(cls, hex_str: str) -> MerklePath:
        """Parse a BRC-71 compact binary Merkle path.

        Format (binary, all little-endian):
        - 4 bytes: block height
        - 1 byte: tree height (number of levels)
        - For each level:
            - varint: number of nodes at this level
            - For each node:
                - varint: offset
                - 1 byte: flags (0x01 = duplicate, 0x02 = txid hash)
                - If not duplicate: 32 bytes hash

        Args:
            hex_str: Hex-encoded BRC-71 Merkle path.

        Returns:
            MerklePath object.
        """
        import struct
        from io import BytesIO

        from spv_wallet.bsv.transaction import read_varint

        data = bytes.fromhex(hex_str)
        stream = BytesIO(data)

        block_height = struct.unpack("<I", stream.read(4))[0]
        tree_height = struct.unpack("<B", stream.read(1))[0]

        path: list[list[MerklePathNode]] = []

        for _level in range(tree_height):
            n_nodes = read_varint(stream)
            level_nodes: list[MerklePathNode] = []

            for _node in range(n_nodes):
                offset = read_varint(stream)
                flags = struct.unpack("<B", stream.read(1))[0]
                is_duplicate = bool(flags & 0x01)
                is_txid = bool(flags & 0x02)

                if is_duplicate:
                    node = MerklePathNode(
                        offset=offset, duplicate=True
                    )
                else:
                    hash_bytes = stream.read(32)
                    node = MerklePathNode(
                        offset=offset,
                        hash=hash_bytes[::-1].hex(),  # Convert to display order
                        txid=is_txid,
                    )

                level_nodes.append(node)

            path.append(level_nodes)

        return cls(block_height=block_height, path=path)

    def compute_root(self, txid: str | None = None) -> str:
        """Compute the Merkle root from this path.

        Walks up the tree, combining sibling hashes at each level
        to arrive at the root hash.

        Args:
            txid: Optional txid to use as the starting leaf hash.
                  If None, extracts it from the path's txid-flagged node.

        Returns:
            The computed Merkle root as a hex string (display order).

        Raises:
            ValueError: If the path is empty or the txid cannot be found.
        """
        if not self.path:
            msg = "Empty Merkle path"
            raise ValueError(msg)

        # Find the target hash at the leaf level
        working_hash, working_offset = self._find_leaf(txid)

        # Walk up the tree
        for level_idx in range(len(self.path)):
            level = self.path[level_idx]

            # Find the sibling
            if working_offset % 2 == 0:
                sibling_offset = working_offset + 1
            else:
                sibling_offset = working_offset - 1

            sibling_hash = self._find_hash_at_level(
                level, sibling_offset, working_hash
            )

            # Combine: lower offset on the left
            if working_offset % 2 == 0:
                left = working_hash
                right = sibling_hash
            else:
                left = sibling_hash
                right = working_hash

            working_hash = sha256d(left + right)
            working_offset = working_offset // 2

        return working_hash[::-1].hex()

    def _find_leaf(self, txid: str | None) -> tuple[bytes, int]:
        """Find the target leaf hash and offset.

        Returns:
            Tuple of (hash_bytes_internal_order, offset).
        """
        if txid is not None:
            # Use provided txid (convert from display to internal byte order)
            leaf_hash = bytes.fromhex(txid)[::-1]
            # Find offset in leaf level
            for node in self.path[0]:
                if node.txid or node.hash == txid:
                    return leaf_hash, node.offset
            # Default to offset 0 if not found in path
            return leaf_hash, 0

        # Find txid-flagged node in leaf level
        for node in self.path[0]:
            if node.txid:
                return bytes.fromhex(node.hash)[::-1], node.offset

        msg = "No txid node found in leaf level"
        raise ValueError(msg)

    def _find_hash_at_level(
        self, level: list[MerklePathNode], offset: int, current: bytes
    ) -> bytes:
        """Find the hash for a given offset at a level.

        If the node is marked as duplicate, returns the current hash.
        """
        for node in level:
            if node.offset == offset:
                if node.duplicate:
                    return current
                return bytes.fromhex(node.hash)[::-1]

        # If sibling not explicitly provided, it's a duplicate
        return current


# ---------------------------------------------------------------------------
# Standalone verification function
# ---------------------------------------------------------------------------


def verify_merkle_path(
    txid: str,
    merkle_path: MerklePath,
    expected_root: str,
) -> bool:
    """Verify that a txid is included in a block via its Merkle path.

    Args:
        txid: The transaction ID (display hex).
        merkle_path: The MerklePath proof.
        expected_root: The expected Merkle root (display hex).

    Returns:
        True if the computed root matches the expected root.
    """
    computed = merkle_path.compute_root(txid)
    return computed == expected_root


def compute_merkle_root(tx_hashes: list[bytes]) -> bytes:
    """Compute the Merkle root from a list of transaction hashes.

    Args:
        tx_hashes: List of 32-byte transaction hashes (internal byte order).

    Returns:
        The 32-byte Merkle root (internal byte order).

    Raises:
        ValueError: If the input list is empty.
    """
    if not tx_hashes:
        msg = "Cannot compute Merkle root from empty list"
        raise ValueError(msg)

    hashes = list(tx_hashes)

    while len(hashes) > 1:
        if len(hashes) % 2 != 0:
            hashes.append(hashes[-1])  # Duplicate last hash if odd count

        next_level: list[bytes] = []
        for i in range(0, len(hashes), 2):
            combined = sha256d(hashes[i] + hashes[i + 1])
            next_level.append(combined)
        hashes = next_level

    return hashes[0]
