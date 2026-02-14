"""ARC data models — TXInfo, TXStatus, fee policy.

Data classes representing ARC API request/response objects.
Matches the ARC v1 API contract from the SPV Wallet Go reference.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Transaction status enum
# ---------------------------------------------------------------------------


class TXStatus(enum.StrEnum):
    """ARC transaction status codes.

    Lifecycle: UNKNOWN → QUEUED → RECEIVED → STORED → ANNOUNCED_TO_NETWORK
               → REQUESTED_BY_NETWORK → SENT_TO_NETWORK → ACCEPTED_BY_NETWORK
               → SEEN_ON_NETWORK → MINED → CONFIRMED → REJECTED
    """

    UNKNOWN = "UNKNOWN"
    QUEUED = "QUEUED"
    RECEIVED = "RECEIVED"
    STORED = "STORED"
    ANNOUNCED_TO_NETWORK = "ANNOUNCED_TO_NETWORK"
    REQUESTED_BY_NETWORK = "REQUESTED_BY_NETWORK"
    SENT_TO_NETWORK = "SENT_TO_NETWORK"
    ACCEPTED_BY_NETWORK = "ACCEPTED_BY_NETWORK"
    SEEN_ON_NETWORK = "SEEN_ON_NETWORK"
    MINED = "MINED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"

    @classmethod
    def from_string(cls, value: str) -> TXStatus:
        """Parse a status string, returning UNKNOWN for unrecognised values."""
        try:
            return cls(value)
        except ValueError:
            return cls.UNKNOWN


# ---------------------------------------------------------------------------
# TXInfo — ARC response for broadcast / query
# ---------------------------------------------------------------------------


@dataclass
class TXInfo:
    """ARC transaction info returned from broadcast and query endpoints.

    Attributes:
        txid: Transaction ID (hex).
        tx_status: Current status string (maps to TXStatus).
        block_hash: Block hash if mined.
        block_height: Block height if mined.
        merkle_path: BRC-71 Merkle path if mined.
        timestamp: Unix timestamp of the status.
        competing_txs: List of competing transaction IDs (double-spend).
        extra_info: Additional info from ARC.
    """

    txid: str = ""
    tx_status: str = ""
    block_hash: str = ""
    block_height: int = 0
    merkle_path: str = ""
    timestamp: int = 0
    competing_txs: list[str] = field(default_factory=list)
    extra_info: str = ""

    @property
    def status(self) -> TXStatus:
        """Parse tx_status string into TXStatus enum."""
        return TXStatus.from_string(self.tx_status)

    @property
    def is_mined(self) -> bool:
        """Check if the transaction has been mined."""
        return self.status in (TXStatus.MINED, TXStatus.CONFIRMED)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TXInfo:
        """Create TXInfo from an ARC JSON response dict."""
        return cls(
            txid=data.get("txid", ""),
            tx_status=data.get("txStatus", data.get("tx_status", "")),
            block_hash=data.get("blockHash", data.get("block_hash", "")),
            block_height=data.get("blockHeight", data.get("block_height", 0)),
            merkle_path=data.get("merklePath", data.get("merkle_path", "")),
            timestamp=data.get("timestamp", 0),
            competing_txs=data.get("competingTxs", data.get("competing_txs", [])),
            extra_info=data.get("extraInfo", data.get("extra_info", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict matching ARC JSON format."""
        return {
            "txid": self.txid,
            "txStatus": self.tx_status,
            "blockHash": self.block_hash,
            "blockHeight": self.block_height,
            "merklePath": self.merkle_path,
            "timestamp": self.timestamp,
            "competingTxs": self.competing_txs,
            "extraInfo": self.extra_info,
        }


# ---------------------------------------------------------------------------
# Fee unit — from ARC policy
# ---------------------------------------------------------------------------


@dataclass
class FeeUnit:
    """Mining fee rate from ARC policy endpoint.

    Attributes:
        satoshis: Satoshis per `bytes` unit (e.g. 1).
        bytes: Byte unit size (e.g. 1000 → 1 sat/1000 bytes).
    """

    satoshis: int = 1
    bytes: int = 1000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FeeUnit:
        """Create FeeUnit from an ARC policy mining fee dict."""
        return cls(
            satoshis=data.get("satoshis", 1),
            bytes=data.get("bytes", 1000),
        )

    def fee_for_size(self, size_bytes: int) -> int:
        """Calculate the fee for a given transaction size.

        Returns:
            Fee in satoshis (rounded up).
        """
        return max(1, (size_bytes * self.satoshis + self.bytes - 1) // self.bytes)


# ---------------------------------------------------------------------------
# Policy response
# ---------------------------------------------------------------------------


@dataclass
class PolicyResponse:
    """ARC policy response (/v1/policy).

    Attributes:
        max_script_size_policy: Maximum script size.
        max_tx_size_policy: Maximum transaction size in bytes.
        mining_fee: Fee unit for mining.
    """

    max_script_size_policy: int = 100_000_000
    max_tx_size_policy: int = 10_000_000
    mining_fee: FeeUnit = field(default_factory=FeeUnit)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyResponse:
        """Create PolicyResponse from ARC JSON."""
        policy = data.get("policy", data)
        mining_fee_data = policy.get("miningFee", policy.get("mining_fee", {}))
        return cls(
            max_script_size_policy=policy.get(
                "maxScriptSizePolicy", policy.get("max_script_size_policy", 100_000_000)
            ),
            max_tx_size_policy=policy.get(
                "maxTxSizePolicy", policy.get("max_tx_size_policy", 10_000_000)
            ),
            mining_fee=FeeUnit.from_dict(mining_fee_data) if mining_fee_data else FeeUnit(),
        )
