"""Destination service — BIP32 address derivation and management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from spv_wallet.bsv.address import pubkey_to_address
from spv_wallet.bsv.keys import ExtendedKey
from spv_wallet.bsv.script import p2pkh_lock_script_from_pubkey
from spv_wallet.config.settings import Network
from spv_wallet.engine.models.destination import Destination
from spv_wallet.errors.spv_errors import SPVError
from spv_wallet.utils.crypto import sha256

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine

ErrDestinationNotFound = SPVError(
    "destination not found", status_code=404, code="destination-not-found"
)


class DestinationService:
    """Business logic for BIP32-derived destination addresses.

    Mirrors the Go engine destination.go service:
    - Derive child key from xPub at chain/index
    - Generate P2PKH address and locking script
    - Track derivation metadata
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    @property
    def _testnet(self) -> bool:
        """Whether the engine is configured for testnet."""
        return self._engine.config.network == Network.TESTNET

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def new_destination(
        self,
        raw_xpub: str,
        *,
        chain: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Destination:
        """Derive the next destination address for an xPub.

        Automatically increments the xPub's chain counter.

        Args:
            raw_xpub: The Base58Check xPub string.
            chain: 0 = external (receiving), 1 = internal (change).
            metadata: Optional metadata to attach.

        Returns:
            The persisted Destination model.
        """
        from spv_wallet.bsv.keys import xpub_id

        xpub_hash = xpub_id(raw_xpub)

        # Reserve the next index from the xPub service
        xpub_svc = self._engine.xpub_service
        num = await xpub_svc.increment_chain(xpub_hash, chain=chain)

        # Derive child key: xpub / chain / num
        xpub_key = ExtendedKey.from_string(raw_xpub)
        child = xpub_key.derive_child(chain).derive_child(num)
        pubkey = child.public_key()

        # Generate address and locking script
        address = pubkey_to_address(pubkey, testnet=self._testnet)
        locking_script = p2pkh_lock_script_from_pubkey(pubkey)
        locking_script_hex = locking_script.hex()

        # ID is SHA-256 of the locking script hex
        dest_id = sha256(locking_script_hex.encode("utf-8")).hex()

        dest = Destination(
            id=dest_id,
            xpub_id=xpub_hash,
            locking_script=locking_script_hex,
            type="pubkeyhash",
            chain=chain,
            num=num,
            address=address,
        )
        if metadata:
            dest.metadata_ = metadata

        async with self._engine.datastore.session() as session:
            session.add(dest)
            await session.commit()
            await session.refresh(dest)

        return dest

    async def new_destination_at(
        self,
        raw_xpub: str,
        *,
        chain: int,
        num: int,
        metadata: dict[str, Any] | None = None,
    ) -> Destination:
        """Derive a destination at a specific chain/num (no counter increment).

        Args:
            raw_xpub: The Base58Check xPub string.
            chain: BIP32 chain (0 or 1).
            num: BIP32 index.
            metadata: Optional metadata.

        Returns:
            The persisted Destination model.
        """
        from spv_wallet.bsv.keys import xpub_id

        xpub_hash = xpub_id(raw_xpub)

        xpub_key = ExtendedKey.from_string(raw_xpub)
        child = xpub_key.derive_child(chain).derive_child(num)
        pubkey = child.public_key()

        address = pubkey_to_address(pubkey, testnet=self._testnet)
        locking_script = p2pkh_lock_script_from_pubkey(pubkey)
        locking_script_hex = locking_script.hex()
        dest_id = sha256(locking_script_hex.encode("utf-8")).hex()

        # Return existing if already derived
        existing = await self.get_destination(dest_id)
        if existing is not None:
            return existing

        dest = Destination(
            id=dest_id,
            xpub_id=xpub_hash,
            locking_script=locking_script_hex,
            type="pubkeyhash",
            chain=chain,
            num=num,
            address=address,
        )
        if metadata:
            dest.metadata_ = metadata

        async with self._engine.datastore.session() as session:
            session.add(dest)
            await session.commit()
            await session.refresh(dest)

        return dest

    async def get_destination(self, id_: str) -> Destination | None:
        """Look up a destination by its ID.

        Args:
            id_: The destination ID (SHA-256 of locking script).

        Returns:
            The Destination model, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Destination).where(Destination.id == id_, Destination.deleted_at.is_(None))
            )
            return result.scalar_one_or_none()

    async def get_destination_by_address(self, address: str) -> Destination | None:
        """Look up a destination by its address.

        Args:
            address: The Base58Check P2PKH address.

        Returns:
            The Destination model, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Destination).where(
                    Destination.address == address,
                    Destination.deleted_at.is_(None),
                )
            )
            return result.scalar_one_or_none()

    async def get_destinations_by_xpub(self, xpub_id: str) -> list[Destination]:
        """Get all destinations for an xPub.

        Args:
            xpub_id: The xPubID.

        Returns:
            List of Destination models.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Destination)
                .where(
                    Destination.xpub_id == xpub_id,
                    Destination.deleted_at.is_(None),
                )
                .order_by(Destination.chain, Destination.num)
            )
            return list(result.scalars().all())
