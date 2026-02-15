"""V2 outline models.

Data classes for transaction outline creation — the unsigned
transaction template that gets sent to the client for signing.
"""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class OutlineOutput:
    """A single output in a transaction outline."""

    to: str  # paymail address or raw address
    satoshis: int
    op_return: bytes | None = None  # OP_RETURN data payload
    custom_instructions: list[dict[str, Any]] | None = None


@dataclasses.dataclass(frozen=True)
class OutlineInput:
    """A selected UTXO input for the outline."""

    tx_id: str
    vout: int
    satoshis: int
    estimated_size: int = 148
    custom_instructions: list[dict[str, Any]] | None = None


@dataclasses.dataclass
class TransactionOutline:
    """Unsigned transaction outline returned to the client for signing.

    Contains all inputs (selected UTXOs), outputs (destinations + change),
    and fee information. The client signs the inputs and sends back
    the signed raw hex for recording.
    """

    user_id: str
    inputs: list[OutlineInput]
    outputs: list[OutlineOutput]
    fee: int
    total_input: int
    total_output: int
    change: int

    @property
    def is_valid(self) -> bool:
        """Check that total_input == total_output + fee."""
        return self.total_input == self.total_output + self.fee

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "user_id": self.user_id,
            "inputs": [dataclasses.asdict(i) for i in self.inputs],
            "outputs": [
                {
                    "to": o.to,
                    "satoshis": o.satoshis,
                    "op_return": o.op_return.hex() if o.op_return else None,
                    "custom_instructions": o.custom_instructions,
                }
                for o in self.outputs
            ],
            "fee": self.fee,
            "total_input": self.total_input,
            "total_output": self.total_output,
            "change": self.change,
        }
