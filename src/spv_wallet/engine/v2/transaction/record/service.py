"""V2 record service — verify and persist signed transactions.

Thin wrapper around TxFlow that provides the service-level API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spv_wallet.engine.v2.transaction.record.tx_flow import TxFlow, TxFlowResult

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class RecordService:
    """Record signed transactions — the V2 equivalent of V1's record_transaction.

    Delegates all processing to TxFlow.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine
        self._tx_flow = TxFlow(engine)

    async def record_transaction_outline(
        self,
        user_id: str,
        raw_hex: str,
        *,
        beef_hex: str | None = None,
        broadcast: bool = True,
    ) -> TxFlowResult:
        """Record a signed transaction outline.

        This is the primary entry point after the client has signed an
        outline and sends back the raw hex.

        Args:
            user_id: The user ID.
            raw_hex: Signed raw transaction hex.
            beef_hex: Optional BEEF hex.
            broadcast: Whether to broadcast to ARC.

        Returns:
            TxFlowResult with all created records and broadcast status.
        """
        return await self._tx_flow.process(
            user_id,
            raw_hex,
            beef_hex=beef_hex,
            broadcast=broadcast,
        )
