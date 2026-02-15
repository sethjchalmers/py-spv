"""V2 TxSync service — handle ARC callbacks and Merkle paths.

Mirrors Go's ``engine/v2/transaction/txsync/``.
Processes ARC broadcast callbacks to update transaction status,
parse Merkle paths, and verify Merkle roots via BHS.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from spv_wallet.engine.v2.database.models import TxStatusV2
from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository
from spv_wallet.errors.definitions import ErrTransactionNotFound

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class TxSyncService:
    """Handle ARC callbacks for V2 transactions.

    When ARC sends a callback (transaction seen on network, mined, etc.),
    this service updates the tracked transaction status and Merkle proof data.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine
        self._tx_repo = TransactionRepository(engine.datastore)

    async def handle_arc_callback(
        self,
        txid: str,
        tx_status: str,
        *,
        block_height: int | None = None,
        block_hash: str | None = None,
        merkle_path: str | None = None,
    ) -> None:
        """Process an ARC broadcast callback.

        Args:
            txid: The transaction ID.
            tx_status: ARC status string (SEEN_ON_NETWORK, MINED, etc.).
            block_height: Block height if mined.
            block_hash: Block hash if mined.
            merkle_path: BRC-71 Merkle path hex if mined.

        Raises:
            SPVError: If transaction not found.
        """
        # Verify transaction exists
        existing = await self._tx_repo.get_transaction(txid)
        if existing is None:
            raise ErrTransactionNotFound

        # Map ARC status to V2 status
        v2_status = self._map_arc_status(tx_status)

        # Build update values
        update_values: dict[str, Any] = {"tx_status": v2_status}
        if block_height is not None:
            update_values["block_height"] = block_height
        if block_hash is not None:
            update_values["block_hash"] = block_hash

        await self._tx_repo.update_transaction(txid, **update_values)

        # If mined and we have a Merkle path, verify the root via BHS
        if v2_status == TxStatusV2.MINED.value and merkle_path and block_height:
            await self._verify_merkle_root(merkle_path, block_height)

    async def sync_unconfirmed(self) -> int:
        """Query ARC for status updates on all broadcasted transactions.

        Returns the number of transactions that were updated.
        """
        broadcasted = await self._tx_repo.list_transactions(
            status=TxStatusV2.BROADCASTED.value,
            page_size=100,
        )

        updated = 0
        chain = self._engine.chain_service
        if chain is None:
            return 0

        for tx in broadcasted:
            try:
                info = await chain.query_transaction(tx.id)
                if info and info.get("txStatus") != TxStatusV2.BROADCASTED.value:
                    await self.handle_arc_callback(
                        tx.id,
                        info.get("txStatus", ""),
                        block_height=info.get("blockHeight"),
                        block_hash=info.get("blockHash"),
                        merkle_path=info.get("merklePath"),
                    )
                    updated += 1
            except Exception:
                logger.debug("Failed to sync tx %s, skipping", tx.id)
                continue  # Skip failed queries

        return updated

    async def _verify_merkle_root(self, merkle_path_hex: str, block_height: int) -> bool:
        """Verify Merkle root via BHS (best-effort)."""
        chain = self._engine.chain_service
        if chain is None or chain.bhs is None:
            return False

        try:
            from spv_wallet.bsv.merkle import MerklePath

            path = MerklePath.from_hex(merkle_path_hex)
            root = path.compute_root()
            return await chain.bhs.is_valid_root(root, block_height)
        except Exception:
            return False

    @staticmethod
    def _map_arc_status(arc_status: str) -> str:
        """Map ARC status string to V2 TxStatusV2 value."""
        mapping = {
            "SEEN_ON_NETWORK": TxStatusV2.SEEN_ON_NETWORK.value,
            "MINED": TxStatusV2.MINED.value,
            "REJECTED": TxStatusV2.REJECTED.value,
            "DOUBLE_SPEND_ATTEMPTED": TxStatusV2.PROBLEMATIC.value,
        }
        return mapping.get(arc_status, arc_status)
