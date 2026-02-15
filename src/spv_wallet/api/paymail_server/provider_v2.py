"""V2 Paymail ServiceProvider implementation.

Server-side handler for incoming paymail protocol requests using
V2 services (users, paymails, addresses).  In V2 the paymail lookup
resolves to a user → derives a fresh address and returns it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from spv_wallet.engine.v2.database.models import AddressV2
from spv_wallet.engine.v2.database.repository.addresses import AddressRepository
from spv_wallet.errors.definitions import ErrPaymailNotFound, ErrPaymailP2PFailed

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine

logger = logging.getLogger(__name__)


class PaymailServiceProviderV2:
    """V2 paymail protocol handler.

    Resolves paymails via ``PaymailsServiceV2``, derives fresh
    addresses from the user's public key, and records incoming
    P2P transactions via ``RecordService``.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Paymail resolution
    # ------------------------------------------------------------------

    async def get_paymail_by_alias(self, alias: str, domain: str) -> dict:
        """Resolve a paymail alias@domain to a V2 paymail record.

        Returns:
            Dict with ``user_id``, ``alias``, ``domain``, ``pub_key``.

        Raises:
            SPVError: If not found.
        """
        paymail = await self._engine.v2.paymails.get_by_address(alias, domain)
        if paymail is None:
            raise ErrPaymailNotFound

        user = await self._engine.v2.users.get_user(paymail.user_id)
        return {
            "user_id": user.id,
            "alias": paymail.alias,
            "domain": paymail.domain,
            "pub_key": user.pub_key,
            "public_name": paymail.public_name,
            "avatar": paymail.avatar,
        }

    # ------------------------------------------------------------------
    # P2P destination
    # ------------------------------------------------------------------

    async def create_p2p_destination_response(
        self,
        alias: str,
        domain: str,
        satoshis: int,
    ) -> dict:
        """Create a P2P destination response for an incoming payment.

        Derives a new address from the user's public key and persists
        it in the V2 addresses table.

        Returns:
            Dict with ``outputs`` (locking script + satoshis) and ``reference``.
        """
        info = await self.get_paymail_by_alias(alias, domain)
        user_id: str = info["user_id"]
        pub_key: str = info["pub_key"]

        # Derive a fresh P2PKH address from the user's compressed pubkey
        address_str = self._derive_address(pub_key)

        # Persist the address in V2 addresses table
        addr_repo = AddressRepository(self._engine.datastore)
        existing = await addr_repo.get_by_address(address_str)
        if existing is None:
            addr = AddressV2(address=address_str, user_id=user_id)
            await addr_repo.create(addr)

        # Build locking script (P2PKH)
        locking_script = self._p2pkh_locking_script(address_str)

        reference = f"{user_id}:{address_str}"

        return {
            "outputs": [
                {
                    "script": locking_script,
                    "satoshis": satoshis,
                },
            ],
            "reference": reference,
        }

    # ------------------------------------------------------------------
    # Basic address resolution
    # ------------------------------------------------------------------

    async def create_address_resolution_response(
        self,
        alias: str,
        domain: str,
    ) -> dict:
        """Return a Bitcoin address for the paymail handle.

        Returns:
            Dict with ``address``.
        """
        info = await self.get_paymail_by_alias(alias, domain)
        address_str = self._derive_address(info["pub_key"])
        return {"address": address_str}

    # ------------------------------------------------------------------
    # Receive P2P transaction
    # ------------------------------------------------------------------

    async def record_transaction(
        self,
        alias: str,
        domain: str,
        *,
        hex: str = "",  # noqa: A002
        reference: str = "",
        beef: str = "",
    ) -> dict:
        """Record an incoming P2P transaction via V2 RecordService.

        Returns:
            Dict with ``txid`` and ``note``.
        """
        await self.get_paymail_by_alias(alias, domain)

        tx_hex = beef or hex
        if not tx_hex:
            return {"txid": "", "note": "no transaction data provided"}

        try:
            result = await self._engine.v2.record.record_transaction(
                tx_hex,
                beef_hex=beef or None,
            )
            return {"txid": result.transaction.id, "note": "transaction recorded"}
        except Exception:
            logger.exception(
                "Failed to record P2P transaction for %s@%s",
                alias,
                domain,
            )
            raise ErrPaymailP2PFailed  # noqa: B904

    # ------------------------------------------------------------------
    # Merkle root verification
    # ------------------------------------------------------------------

    async def verify_merkle_roots(self, merkle_roots: list[str]) -> bool:
        """Verify Merkle roots via the Block Headers Service."""
        chain = self._engine.chain_service
        if chain is None:
            logger.warning("Chain service not available for Merkle root verification")
            return True

        try:
            return await chain.bhs.verify_merkle_roots(merkle_roots)
        except Exception:
            logger.exception("Merkle root verification failed")
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_address(pub_key: str) -> str:
        """Derive a P2PKH address from a compressed public key."""
        from spv_wallet.bsv.address import pubkey_to_address

        return pubkey_to_address(bytes.fromhex(pub_key))

    @staticmethod
    def _p2pkh_locking_script(address: str) -> str:
        """Build a P2PKH locking script hex for a Base58Check address.

        OP_DUP OP_HASH160 <20-byte-hash> OP_EQUALVERIFY OP_CHECKSIG
        """
        from spv_wallet.bsv.address import address_to_pubkey_hash

        h160 = address_to_pubkey_hash(address)
        return f"76a914{h160.hex()}88ac"
