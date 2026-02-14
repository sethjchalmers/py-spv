"""BSV script building — P2PKH, OP_RETURN, script type detection.

Provides construction and parsing of standard BSV locking/unlocking scripts:
- P2PKH (Pay-to-Public-Key-Hash) lock and unlock scripts
- OP_RETURN (null data) scripts
- Script type detection and classification
"""

from __future__ import annotations

import enum
import struct

from spv_wallet.utils.crypto import hash160

# ---------------------------------------------------------------------------
# Opcodes
# ---------------------------------------------------------------------------


class OpCode(int, enum.Enum):
    """Commonly used Bitcoin opcodes."""

    OP_0 = 0x00
    OP_FALSE = 0x00
    OP_PUSHDATA1 = 0x4C
    OP_PUSHDATA2 = 0x4D
    OP_PUSHDATA4 = 0x4E
    OP_RETURN = 0x6A
    OP_DUP = 0x76
    OP_EQUAL = 0x87
    OP_EQUALVERIFY = 0x88
    OP_HASH160 = 0xA9
    OP_CHECKSIG = 0xAC


# ---------------------------------------------------------------------------
# Script Type
# ---------------------------------------------------------------------------


class ScriptType(enum.StrEnum):
    """Known script types."""

    P2PKH = "pubkeyhash"
    NULL_DATA = "nulldata"
    P2PK = "pubkey"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Data push helpers
# ---------------------------------------------------------------------------


def push_data(data: bytes) -> bytes:
    """Encode a data push operation using minimal encoding rules.

    Args:
        data: Arbitrary data bytes.

    Returns:
        The opcode(s) + data for a minimal push of *data*.
    """
    length = len(data)
    if length == 0:
        return bytes([OpCode.OP_0])
    if length <= 0x4B:
        return bytes([length]) + data
    if length <= 0xFF:
        return bytes([OpCode.OP_PUSHDATA1, length]) + data
    if length <= 0xFFFF:
        return bytes([OpCode.OP_PUSHDATA2]) + struct.pack("<H", length) + data
    return bytes([OpCode.OP_PUSHDATA4]) + struct.pack("<I", length) + data


# ---------------------------------------------------------------------------
# P2PKH scripts
# ---------------------------------------------------------------------------


def p2pkh_lock_script(pubkey_hash: bytes) -> bytes:
    """Build a P2PKH locking script (scriptPubKey).

    OP_DUP OP_HASH160 <20 bytes> OP_EQUALVERIFY OP_CHECKSIG

    Args:
        pubkey_hash: 20-byte RIPEMD160(SHA256(pubkey)).

    Returns:
        25-byte locking script.
    """
    if len(pubkey_hash) != 20:
        msg = f"pubkey_hash must be 20 bytes, got {len(pubkey_hash)}"
        raise ValueError(msg)
    return (
        bytes([OpCode.OP_DUP, OpCode.OP_HASH160])
        + push_data(pubkey_hash)
        + bytes([OpCode.OP_EQUALVERIFY, OpCode.OP_CHECKSIG])
    )


def p2pkh_lock_script_from_pubkey(pubkey: bytes) -> bytes:
    """Build a P2PKH locking script from a public key.

    Args:
        pubkey: 33-byte compressed or 65-byte uncompressed public key.
    """
    return p2pkh_lock_script(hash160(pubkey))


def p2pkh_unlock_script(signature: bytes, pubkey: bytes) -> bytes:
    """Build a P2PKH unlocking script (scriptSig).

    <sig> <pubkey>

    Args:
        signature: DER-encoded signature (with sighash byte appended).
        pubkey: 33-byte compressed public key.
    """
    return push_data(signature) + push_data(pubkey)


# ---------------------------------------------------------------------------
# OP_RETURN scripts
# ---------------------------------------------------------------------------


def op_return_script(*data_items: bytes) -> bytes:
    """Build an OP_RETURN (null data) script.

    ``OP_FALSE OP_RETURN <push data1> <push data2> ...``

    Args:
        data_items: One or more byte strings to push after OP_RETURN.

    Returns:
        The complete OP_RETURN locking script.
    """
    script = bytes([OpCode.OP_FALSE, OpCode.OP_RETURN])
    for item in data_items:
        script += push_data(item)
    return script


# ---------------------------------------------------------------------------
# Script type detection
# ---------------------------------------------------------------------------


def detect_script_type(script: bytes) -> ScriptType:
    """Detect the type of a locking script.

    Recognises:
    - P2PKH: ``OP_DUP OP_HASH160 <20> ... OP_EQUALVERIFY OP_CHECKSIG``
    - NULL_DATA: ``OP_FALSE OP_RETURN ...`` or ``OP_RETURN ...``
    - P2PK: ``<33|65> OP_CHECKSIG``

    Returns:
        The detected :class:`ScriptType`.
    """
    if len(script) == 0:
        return ScriptType.UNKNOWN

    # P2PKH (exactly 25 bytes with known pattern)
    if (
        len(script) == 25
        and script[0] == OpCode.OP_DUP
        and script[1] == OpCode.OP_HASH160
        and script[2] == 0x14  # push 20 bytes
        and script[23] == OpCode.OP_EQUALVERIFY
        and script[24] == OpCode.OP_CHECKSIG
    ):
        return ScriptType.P2PKH

    # OP_RETURN variants
    if script[0] == OpCode.OP_RETURN:
        return ScriptType.NULL_DATA
    if len(script) >= 2 and script[0] == OpCode.OP_FALSE and script[1] == OpCode.OP_RETURN:
        return ScriptType.NULL_DATA

    # P2PK (compressed or uncompressed)
    if (
        len(script) == 35
        and script[0] == 0x21  # push 33 bytes
        and script[34] == OpCode.OP_CHECKSIG
    ):
        return ScriptType.P2PK
    if (
        len(script) == 67
        and script[0] == 0x41  # push 65 bytes
        and script[66] == OpCode.OP_CHECKSIG
    ):
        return ScriptType.P2PK

    return ScriptType.UNKNOWN


def extract_pubkey_hash(script: bytes) -> bytes | None:
    """Extract the 20-byte pubkey hash from a P2PKH locking script.

    Returns None if the script is not P2PKH.
    """
    if detect_script_type(script) != ScriptType.P2PKH:
        return None
    return script[3:23]
