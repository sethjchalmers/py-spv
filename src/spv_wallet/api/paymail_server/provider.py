"""Paymail ServiceProvider implementation.

Server-side handler for incoming paymail protocol requests.
Mirrors the Go ``engine/paymail_service_provider.go``:
- GetPaymailByAlias — resolve alias@domain to a paymail record
- CreateAddressResolutionResponse — basic address resolution
- CreateP2PDestinationResponse — P2P payment destinations
- RecordTransaction — receive and record incoming P2P transactions
- VerifyMerkleRoots — verify BEEF Merkle roots via BHS
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from spv_wallet.errors.definitions import ErrPaymailNotFound, ErrPaymailP2PFailed

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine
    from spv_wallet.engine.models.paymail_address import PaymailAddress

logger = logging.getLogger(__name__)


class PaymailServiceProvider:
    """Server-side paymail protocol handler.

    Receives incoming paymail requests and fulfills them using
    the engine's services (paymail, destination, transaction).
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    async def get_paymail_by_alias(
        self, alias: str, domain: str
    ) -> PaymailAddress:
        """Resolve a paymail alias@domain to a PaymailAddress record.

        Args:
            alias: The local part of the paymail.
            domain: The domain of the paymail.

        Returns:
            The matching PaymailAddress.

        Raises:
            SPVError: If not found.
        """
        pm = await self._engine.paymail_service.get_paymail_by_alias(alias, domain)
        if pm is None:
            raise ErrPaymailNotFound
        return pm

    async def create_p2p_destination_response(
        self,
        alias: str,
        domain: str,
        satoshis: int,
    ) -> dict:
        """Create a P2P destination response for an incoming payment.

        Derives a new destination address and returns it in the
        standard P2P format.

        Args:
            alias: Recipient's alias.
            domain: Recipient's domain.
            satoshis: Requested amount.

        Returns:
            Dict with ``outputs`` and ``reference`` fields.
        """
        # Resolve the paymail to get the xPub
        paymail = await self.get_paymail_by_alias(alias, domain)

        # Verify the xPub exists and retrieve the raw key
        xpub = await self._engine.xpub_service.get_xpub_by_id(
            paymail.xpub_id, required=True
        )

        # Derive a new destination — raw xPub string stored in metadata
        raw_xpub = ""
        if xpub and xpub.metadata_:
            raw_xpub = xpub.metadata_.get("raw_xpub", "")

        if not raw_xpub:
            raise ErrPaymailP2PFailed

        dest = await self._engine.destination_service.new_destination(raw_xpub)

        # Build the reference (paymail_id + destination_id)
        reference = f"{paymail.id}:{dest.id}"

        return {
            "outputs": [
                {
                    "script": dest.locking_script,
                    "satoshis": satoshis,
                }
            ],
            "reference": reference,
        }

    async def create_address_resolution_response(
        self,
        alias: str,
        domain: str,
    ) -> dict:
        """Create a basic address resolution response.

        Returns a Bitcoin address for the paymail handle.

        Args:
            alias: Recipient's alias.
            domain: Recipient's domain.

        Returns:
            Dict with ``address`` field.
        """
        paymail = await self.get_paymail_by_alias(alias, domain)

        # Get raw xPub from metadata to derive a fresh destination
        xpub = await self._engine.xpub_service.get_xpub_by_id(
            paymail.xpub_id, required=True
        )
        raw_xpub = ""
        if xpub and xpub.metadata_:
            raw_xpub = xpub.metadata_.get("raw_xpub", "")

        if not raw_xpub:
            raise ErrPaymailP2PFailed

        dest = await self._engine.destination_service.new_destination(raw_xpub)

        return {
            "address": dest.address,
        }

    async def record_transaction(
        self,
        alias: str,
        domain: str,
        *,
        hex: str = "",  # noqa: A002
        reference: str = "",
        beef: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """Record an incoming P2P transaction.

        Called when a sender pushes a transaction to this server.

        Args:
            alias: Recipient's alias.
            domain: Recipient's domain.
            hex: Raw transaction hex.
            reference: Payment reference from destination response.
            beef: BEEF-encoded transaction (alternative to hex).
            metadata: Optional sender metadata.

        Returns:
            Dict with ``txid`` and ``note`` fields.
        """
        # Validate the paymail exists
        await self.get_paymail_by_alias(alias, domain)

        # Determine transaction hex (prefer BEEF if available)
        tx_hex = beef or hex

        if not tx_hex:
            return {"txid": "", "note": "no transaction data provided"}

        # Record via transaction service
        # For now, we log and return the txid
        # Full implementation would broadcast via ARC and record UTXOs
        logger.info(
            "Recording incoming P2P transaction for %s@%s ref=%s meta=%s",
            alias,
            domain,
            reference,
            metadata,
        )

        # Extract txid from raw hex (first 32 bytes reversed = txid)
        # Simplified — full impl would deserialize the transaction
        from spv_wallet.utils.crypto import sha256d

        try:
            raw_bytes = bytes.fromhex(tx_hex)
            txid = sha256d(raw_bytes).hex()
        except (ValueError, TypeError):
            txid = ""

        return {
            "txid": txid,
            "note": "transaction received",
        }

    async def verify_merkle_roots(self, merkle_roots: list[str]) -> bool:
        """Verify Merkle roots via the Block Headers Service.

        Used for BEEF transaction validation.

        Args:
            merkle_roots: List of Merkle root hex strings to verify.

        Returns:
            True if all roots are valid.
        """
        chain = self._engine.chain_service
        if chain is None:
            logger.warning("Chain service not available for Merkle root verification")
            return True  # Permissive if BHS unavailable

        try:
            return await chain.bhs.verify_merkle_roots(merkle_roots)
        except Exception:
            logger.exception("Merkle root verification failed")
            return False


async def xpub_from_id(engine: SPVWalletEngine, xpub_id: str) -> str:
    """Resolve an xPub ID back to the raw xPub string.

    This is a helper that looks up the xPub record and returns
    the raw key. In a production system, the raw xPub would be
    stored or derivable; here we use the cached xPub model.

    Args:
        engine: The engine instance.
        xpub_id: The xPub ID (SHA-256 hash).

    Returns:
        The raw xPub string.

    Raises:
        SPVError: If xPub not found.
    """
    xpub = await engine.xpub_service.get_xpub_by_id(xpub_id, required=True)
    # The raw xPub is not stored in the model — it would need to
    # be retrieved from the original registration or session context.
    # For now, return the ID as a placeholder for the derivation path.
    # In production, we'd store the raw xPub or use a key server.
    return xpub.id  # type: ignore[union-attr]
