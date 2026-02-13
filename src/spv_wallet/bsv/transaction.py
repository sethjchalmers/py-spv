"""Transaction serialisation — raw hex, EF hex, BEEF format.

Provides pure-Python Bitcoin transaction serialization and deserialization:
- TxInput / TxOutput data classes
- Transaction class with serialize / deserialize / txid computation
- VarInt encoding/decoding
- Raw hex format support
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from io import BytesIO

from spv_wallet.utils.crypto import sha256d

# ---------------------------------------------------------------------------
# VarInt encoding / decoding
# ---------------------------------------------------------------------------


def encode_varint(n: int) -> bytes:
    """Encode an integer as a Bitcoin-style variable-length integer."""
    if n < 0xFD:
        return struct.pack("<B", n)
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    if n <= 0xFFFFFFFF:
        return b"\xfe" + struct.pack("<I", n)
    return b"\xff" + struct.pack("<Q", n)


def read_varint(stream: BytesIO) -> int:
    """Read a Bitcoin-style variable-length integer from a byte stream."""
    first = stream.read(1)
    if len(first) == 0:
        msg = "Unexpected end of stream reading varint"
        raise ValueError(msg)
    n = first[0]
    if n < 0xFD:
        return n
    if n == 0xFD:
        return struct.unpack("<H", stream.read(2))[0]
    if n == 0xFE:
        return struct.unpack("<I", stream.read(4))[0]
    return struct.unpack("<Q", stream.read(8))[0]


# ---------------------------------------------------------------------------
# Outpoint (txid + vout reference)
# ---------------------------------------------------------------------------

# Default sequence: 0xFFFFFFFF (no RBF)
DEFAULT_SEQUENCE = 0xFFFFFFFF

# The null previous outpoint used in coinbase transactions
COINBASE_TXID = b"\x00" * 32


# ---------------------------------------------------------------------------
# TxInput
# ---------------------------------------------------------------------------


@dataclass
class TxInput:
    """A transaction input.

    Attributes:
        prev_tx_id: 32-byte hash of the previous transaction (internal byte order).
        prev_tx_out_index: Index of the output in the previous transaction.
        script_sig: Unlocking script (scriptSig).
        sequence: Sequence number (default 0xFFFFFFFF).
    """

    prev_tx_id: bytes
    prev_tx_out_index: int
    script_sig: bytes = b""
    sequence: int = DEFAULT_SEQUENCE

    @property
    def prev_tx_id_hex(self) -> str:
        """Previous transaction ID in display (reversed) hex."""
        return self.prev_tx_id[::-1].hex()

    @property
    def is_coinbase(self) -> bool:
        """Check if this is a coinbase input."""
        return self.prev_tx_id == COINBASE_TXID and self.prev_tx_out_index == 0xFFFFFFFF

    def serialize(self) -> bytes:
        """Serialize the input to bytes."""
        result = self.prev_tx_id
        result += struct.pack("<I", self.prev_tx_out_index)
        result += encode_varint(len(self.script_sig))
        result += self.script_sig
        result += struct.pack("<I", self.sequence)
        return result

    @classmethod
    def deserialize(cls, stream: BytesIO) -> TxInput:
        """Deserialize a transaction input from a byte stream."""
        prev_tx_id = stream.read(32)
        if len(prev_tx_id) != 32:
            msg = "Unexpected end of stream reading prev_tx_id"
            raise ValueError(msg)
        prev_tx_out_index = struct.unpack("<I", stream.read(4))[0]
        script_len = read_varint(stream)
        script_sig = stream.read(script_len)
        sequence = struct.unpack("<I", stream.read(4))[0]
        return cls(
            prev_tx_id=prev_tx_id,
            prev_tx_out_index=prev_tx_out_index,
            script_sig=script_sig,
            sequence=sequence,
        )


# ---------------------------------------------------------------------------
# TxOutput
# ---------------------------------------------------------------------------


@dataclass
class TxOutput:
    """A transaction output.

    Attributes:
        value: Output value in satoshis.
        script_pubkey: Locking script (scriptPubKey).
    """

    value: int
    script_pubkey: bytes

    def serialize(self) -> bytes:
        """Serialize the output to bytes."""
        result = struct.pack("<q", self.value)
        result += encode_varint(len(self.script_pubkey))
        result += self.script_pubkey
        return result

    @classmethod
    def deserialize(cls, stream: BytesIO) -> TxOutput:
        """Deserialize a transaction output from a byte stream."""
        value = struct.unpack("<q", stream.read(8))[0]
        script_len = read_varint(stream)
        script_pubkey = stream.read(script_len)
        return cls(value=value, script_pubkey=script_pubkey)


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


@dataclass
class Transaction:
    """A Bitcoin transaction.

    Attributes:
        version: Transaction version (default 1).
        inputs: List of transaction inputs.
        outputs: List of transaction outputs.
        locktime: Transaction locktime (default 0).
    """

    version: int = 1
    inputs: list[TxInput] = field(default_factory=list)
    outputs: list[TxOutput] = field(default_factory=list)
    locktime: int = 0

    def serialize(self) -> bytes:
        """Serialize the transaction to raw bytes."""
        result = struct.pack("<i", self.version)
        result += encode_varint(len(self.inputs))
        for inp in self.inputs:
            result += inp.serialize()
        result += encode_varint(len(self.outputs))
        for out in self.outputs:
            result += out.serialize()
        result += struct.pack("<I", self.locktime)
        return result

    def to_hex(self) -> str:
        """Serialize to hex string."""
        return self.serialize().hex()

    @classmethod
    def deserialize(cls, stream: BytesIO) -> Transaction:
        """Deserialize a transaction from a byte stream."""
        version = struct.unpack("<i", stream.read(4))[0]
        n_inputs = read_varint(stream)
        inputs = [TxInput.deserialize(stream) for _ in range(n_inputs)]
        n_outputs = read_varint(stream)
        outputs = [TxOutput.deserialize(stream) for _ in range(n_outputs)]
        locktime = struct.unpack("<I", stream.read(4))[0]
        return cls(version=version, inputs=inputs, outputs=outputs, locktime=locktime)

    @classmethod
    def from_hex(cls, hex_str: str) -> Transaction:
        """Deserialize a transaction from a hex string."""
        raw = bytes.fromhex(hex_str)
        return cls.from_bytes(raw)

    @classmethod
    def from_bytes(cls, data: bytes) -> Transaction:
        """Deserialize a transaction from raw bytes."""
        stream = BytesIO(data)
        return cls.deserialize(stream)

    def txid(self) -> str:
        """Compute the transaction ID (double-SHA256, reversed, hex).

        Returns:
            The 64-character hex txid string (display byte order).
        """
        raw_hash = sha256d(self.serialize())
        return raw_hash[::-1].hex()

    def txid_bytes(self) -> bytes:
        """Compute the transaction ID as 32 bytes (internal byte order)."""
        return sha256d(self.serialize())

    @property
    def size(self) -> int:
        """Transaction size in bytes."""
        return len(self.serialize())

    def add_input(
        self,
        prev_tx_id: bytes,
        prev_tx_out_index: int,
        script_sig: bytes = b"",
        sequence: int = DEFAULT_SEQUENCE,
    ) -> TxInput:
        """Add an input to the transaction.

        Returns:
            The newly created :class:`TxInput`.
        """
        inp = TxInput(
            prev_tx_id=prev_tx_id,
            prev_tx_out_index=prev_tx_out_index,
            script_sig=script_sig,
            sequence=sequence,
        )
        self.inputs.append(inp)
        return inp

    def add_output(self, value: int, script_pubkey: bytes) -> TxOutput:
        """Add an output to the transaction.

        Returns:
            The newly created :class:`TxOutput`.
        """
        out = TxOutput(value=value, script_pubkey=script_pubkey)
        self.outputs.append(out)
        return out
