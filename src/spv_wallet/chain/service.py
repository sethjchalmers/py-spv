"""Combined ARC + BHS chain service.

Composes ARC (transaction broadcasting) and BHS (Merkle root verification)
into a single service for the engine to consume.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spv_wallet.chain.arc.service import ARCService
from spv_wallet.chain.bhs.service import BHSService

if TYPE_CHECKING:
    from spv_wallet.chain.arc.models import FeeUnit, TXInfo
    from spv_wallet.chain.bhs.models import MerkleRootVerification, VerifyMerkleRootsResponse
    from spv_wallet.config.settings import AppConfig


class ChainService:
    """Unified chain service composing ARC + BHS.

    Usage::

        chain = ChainService(config)
        await chain.connect()
        try:
            info = await chain.broadcast(hex)
            ok = await chain.verify_merkle_roots([...])
        finally:
            await chain.close()
    """

    def __init__(self, config: AppConfig) -> None:
        """Initialize the chain service with app config.

        Args:
            config: Application configuration containing arc and bhs settings.
        """
        self._arc = ARCService(config.arc)
        self._bhs = BHSService(config.bhs)

    async def connect(self) -> None:
        """Connect both ARC and BHS HTTP clients."""
        await self._arc.connect()
        await self._bhs.connect()

    async def close(self) -> None:
        """Close both ARC and BHS HTTP clients."""
        await self._arc.close()
        await self._bhs.close()

    @property
    def is_connected(self) -> bool:
        """Check if both services are connected."""
        return self._arc.is_connected and self._bhs.is_connected

    @property
    def arc(self) -> ARCService:
        """Direct access to the ARC service."""
        return self._arc

    @property
    def bhs(self) -> BHSService:
        """Direct access to the BHS service."""
        return self._bhs

    # ------------------------------------------------------------------
    # ARC delegation
    # ------------------------------------------------------------------

    async def broadcast(self, raw_tx: str, *, wait_for: str | None = None) -> TXInfo:
        """Broadcast a transaction via ARC.

        Args:
            raw_tx: Transaction hex.
            wait_for: Override wait strategy.

        Returns:
            TXInfo with broadcast result.
        """
        return await self._arc.broadcast(raw_tx, wait_for=wait_for)

    async def query_transaction(self, txid: str) -> TXInfo:
        """Query transaction status via ARC.

        Args:
            txid: Transaction ID (hex).

        Returns:
            TXInfo with current status.
        """
        return await self._arc.query_transaction(txid)

    async def get_fee_unit(self) -> FeeUnit:
        """Get current mining fee unit from ARC.

        Returns:
            FeeUnit with satoshis/bytes rate.
        """
        return await self._arc.get_fee_unit()

    # ------------------------------------------------------------------
    # BHS delegation
    # ------------------------------------------------------------------

    async def verify_merkle_roots(
        self, roots: list[MerkleRootVerification]
    ) -> VerifyMerkleRootsResponse:
        """Verify Merkle roots via BHS.

        Args:
            roots: List of Merkle root verifications.

        Returns:
            VerifyMerkleRootsResponse with confirmation states.
        """
        return await self._bhs.verify_merkle_roots(roots)

    async def is_valid_root(self, merkle_root: str, block_height: int) -> bool:
        """Verify a single Merkle root.

        Args:
            merkle_root: Merkle root hash (hex).
            block_height: Block height.

        Returns:
            True if confirmed.
        """
        return await self._bhs.is_valid_root(merkle_root, block_height)

    async def healthcheck(self) -> dict[str, str]:
        """Check health of both ARC and BHS.

        Returns:
            Dict with 'arc' and 'bhs' status strings.
        """
        arc_status = "ok" if self._arc.is_connected else "not_connected"
        bhs_healthy = False
        if self._bhs.is_connected:
            bhs_healthy = await self._bhs.healthcheck()
        bhs_status = "ok" if bhs_healthy else "error"

        return {"arc": arc_status, "bhs": bhs_status}
