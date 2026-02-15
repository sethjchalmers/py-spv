"""V2 outlines service — create unsigned transaction outlines.

Mirrors Go's ``engine/v2/transaction/outlines/create_transaction_outline.go``.
The outline is an unsigned transaction template: it selects UTXOs, calculates
fees, resolves paymail destinations, and returns the template for the client
to sign.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository
from spv_wallet.engine.v2.transaction.outlines.models import (
    OutlineInput,
    OutlineOutput,
    TransactionOutline,
)
from spv_wallet.errors.definitions import ErrNotEnoughFunds, ErrOutlineNoOutputs

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


# Default fee rate: 1 sat per 1000 bytes (matches BSV's default mining policy)
DEFAULT_FEE_RATE_SATS = 1
DEFAULT_FEE_RATE_BYTES = 1000

# Estimated sizes (bytes)
_TX_OVERHEAD = 10  # version + locktime + varint counts
_OUTPUT_SIZE = 34  # standard P2PKH output
_OP_RETURN_OVERHEAD = 11  # OP_RETURN output with small payload
_CHANGE_OUTPUT_SIZE = 34


class OutlinesService:
    """Create unsigned transaction outlines for V2 users.

    The outline process:
    1. Validate outputs
    2. Calculate estimated fee
    3. Select UTXOs (oldest-first coin selection)
    4. Compute change
    5. Return TransactionOutline for client signing
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine
        self._tx_repo = TransactionRepository(engine.datastore)

    async def create(
        self,
        user_id: str,
        outputs: list[OutlineOutput],
        *,
        fee_rate_sats: int = DEFAULT_FEE_RATE_SATS,
        fee_rate_bytes: int = DEFAULT_FEE_RATE_BYTES,
    ) -> TransactionOutline:
        """Create an unsigned transaction outline.

        Args:
            user_id: The V2 user ID.
            outputs: Requested outputs.
            fee_rate_sats: Fee rate numerator (satoshis).
            fee_rate_bytes: Fee rate denominator (bytes).

        Returns:
            A TransactionOutline ready for client signing.

        Raises:
            SPVError: If no outputs, not enough funds, etc.
        """
        if not outputs:
            raise ErrOutlineNoOutputs

        # Calculate output total
        total_output = sum(o.satoshis for o in outputs)

        # Estimate transaction size for fee calculation
        num_outputs = len(outputs) + 1  # +1 for change output
        data_outputs = sum(1 for o in outputs if o.op_return is not None)
        regular_outputs = num_outputs - data_outputs

        estimated_size = (
            _TX_OVERHEAD + regular_outputs * _OUTPUT_SIZE + data_outputs * _OP_RETURN_OVERHEAD
        )

        # Select UTXOs — we'll iterate, adding inputs until we cover the cost
        available_utxos = await self._tx_repo.get_utxos_for_selection(user_id)

        selected_inputs: list[OutlineInput] = []
        total_input = 0
        running_size = estimated_size

        for utxo in available_utxos:
            selected_inputs.append(
                OutlineInput(
                    tx_id=utxo.tx_id,
                    vout=utxo.vout,
                    satoshis=utxo.satoshis,
                    estimated_size=utxo.estimated_input_size,
                    custom_instructions=(
                        None  # Could parse utxo.custom_instructions JSON here
                    ),
                ),
            )
            total_input += utxo.satoshis
            running_size += utxo.estimated_input_size

            # Calculate fee with current size
            fee = _calculate_fee(running_size, fee_rate_sats, fee_rate_bytes)

            if total_input >= total_output + fee:
                break

        # Final fee with actual input count
        fee = _calculate_fee(running_size, fee_rate_sats, fee_rate_bytes)

        if total_input < total_output + fee:
            raise ErrNotEnoughFunds

        change = total_input - total_output - fee

        return TransactionOutline(
            user_id=user_id,
            inputs=selected_inputs,
            outputs=list(outputs),
            fee=fee,
            total_input=total_input,
            total_output=total_output,
            change=change,
        )


def _calculate_fee(size_bytes: int, rate_sats: int, rate_bytes: int) -> int:
    """Calculate mining fee: ceil(size * rate_sats / rate_bytes)."""
    return max(1, (size_bytes * rate_sats + rate_bytes - 1) // rate_bytes)
