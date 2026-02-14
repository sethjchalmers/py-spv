"""UTXO service — CRUD, selection, and balance queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from spv_wallet.engine.models.utxo import UTXO
from spv_wallet.errors.definitions import ErrUTXONotFound

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class UTXOService:
    """Business logic for unspent transaction output management.

    Mirrors the Go engine utxo.go service:
    - Create/get/query UTXOs
    - Mark spent
    - Balance aggregation
    - Filtering by xpub, spending status, etc.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def new_utxo(
        self,
        xpub_id: str,
        transaction_id: str,
        output_index: int,
        satoshis: int,
        script_pub_key: str,
        *,
        type_: str = "pubkeyhash",
        destination_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> UTXO:
        """Create a new UTXO record.

        Args:
            xpub_id: Owning xPub ID.
            transaction_id: Transaction ID (txid).
            output_index: Output index (vout).
            satoshis: Value in satoshis.
            script_pub_key: Hex-encoded locking script.
            type_: Script type (default: pubkeyhash).
            destination_id: Associated destination ID.
            metadata: Optional metadata.

        Returns:
            The persisted UTXO model.
        """
        utxo_id = f"{transaction_id}:{output_index}"

        # Return existing if already tracked
        existing = await self.get_utxo(utxo_id)
        if existing is not None:
            return existing

        utxo = UTXO(
            id=utxo_id,
            xpub_id=xpub_id,
            transaction_id=transaction_id,
            output_index=output_index,
            satoshis=satoshis,
            script_pub_key=script_pub_key,
            type=type_,
            destination_id=destination_id,
        )
        if metadata:
            utxo.metadata_ = metadata

        async with self._engine.datastore.session() as session:
            session.add(utxo)
            await session.commit()
            await session.refresh(utxo)

        return utxo

    async def get_utxo(self, id_: str) -> UTXO | None:
        """Look up a UTXO by its composite ID (txid:vout).

        Args:
            id_: The UTXO ID.

        Returns:
            The UTXO model, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(UTXO).where(UTXO.id == id_, UTXO.deleted_at.is_(None))
            )
            return result.scalar_one_or_none()

    async def get_utxos(
        self,
        *,
        xpub_id: str | None = None,
        transaction_id: str | None = None,
        unspent_only: bool = False,
    ) -> list[UTXO]:
        """Query UTXOs with optional filters.

        Args:
            xpub_id: Filter by owning xPub ID.
            transaction_id: Filter by transaction ID.
            unspent_only: If True, only return unspent UTXOs.

        Returns:
            List of matching UTXO models.
        """
        stmt = select(UTXO).where(UTXO.deleted_at.is_(None))

        if xpub_id is not None:
            stmt = stmt.where(UTXO.xpub_id == xpub_id)
        if transaction_id is not None:
            stmt = stmt.where(UTXO.transaction_id == transaction_id)
        if unspent_only:
            stmt = stmt.where(UTXO.spending_tx_id == "")

        stmt = stmt.order_by(UTXO.satoshis.desc())

        async with self._engine.datastore.session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def count_utxos(
        self,
        *,
        xpub_id: str | None = None,
        unspent_only: bool = False,
    ) -> int:
        """Count UTXOs matching filters.

        Args:
            xpub_id: Filter by owning xPub ID.
            unspent_only: If True, only count unspent UTXOs.

        Returns:
            The count of matching UTXOs.
        """
        stmt = select(func.count(UTXO.id)).where(UTXO.deleted_at.is_(None))

        if xpub_id is not None:
            stmt = stmt.where(UTXO.xpub_id == xpub_id)
        if unspent_only:
            stmt = stmt.where(UTXO.spending_tx_id == "")

        async with self._engine.datastore.session() as session:
            result = await session.execute(stmt)
            return result.scalar_one()

    async def mark_spent(
        self, id_: str, spending_tx_id: str
    ) -> UTXO:
        """Mark a UTXO as spent by a transaction.

        Args:
            id_: The UTXO ID (txid:vout).
            spending_tx_id: The transaction ID that spent this UTXO.

        Returns:
            The updated UTXO model.

        Raises:
            SPVError: If UTXO not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(UTXO).where(UTXO.id == id_, UTXO.deleted_at.is_(None))
            )
            utxo = result.scalar_one_or_none()
            if utxo is None:
                raise ErrUTXONotFound

            utxo.spending_tx_id = spending_tx_id
            await session.commit()
            await session.refresh(utxo)

        return utxo

    async def get_balance(self, xpub_id: str) -> int:
        """Get the total unspent balance for an xPub.

        Args:
            xpub_id: The xPubID.

        Returns:
            Total satoshis in unspent UTXOs.
        """
        stmt = (
            select(func.coalesce(func.sum(UTXO.satoshis), 0))
            .where(
                UTXO.xpub_id == xpub_id,
                UTXO.spending_tx_id == "",
                UTXO.deleted_at.is_(None),
            )
        )

        async with self._engine.datastore.session() as session:
            result = await session.execute(stmt)
            return result.scalar_one()

    async def get_unspent_for_draft(
        self, xpub_id: str, *, required_sats: int
    ) -> list[UTXO]:
        """Select unspent UTXOs to cover a required amount.

        Uses a simple greedy approach — largest UTXOs first.

        Args:
            xpub_id: The xPubID.
            required_sats: Minimum satoshis needed.

        Returns:
            List of selected UTXOs.

        Raises:
            SPVError: If insufficient funds.
        """
        from spv_wallet.errors.definitions import ErrNotEnoughFunds

        utxos = await self.get_utxos(
            xpub_id=xpub_id, unspent_only=True
        )

        selected: list[UTXO] = []
        total = 0
        for utxo in utxos:
            if utxo.draft_id:
                continue  # Already reserved
            selected.append(utxo)
            total += utxo.satoshis
            if total >= required_sats:
                return selected

        raise ErrNotEnoughFunds
