"""V2 transactions repository."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update

from spv_wallet.engine.v2.database.models import (
    DataV2,
    TrackedTransaction,
    TxInput,
    UserUTXO,
)

if TYPE_CHECKING:
    from spv_wallet.datastore.client import Datastore


class TransactionRepository:
    """Data access layer for V2 tracked transactions, UTXOs, inputs, and data."""

    def __init__(self, datastore: Datastore) -> None:
        self._ds = datastore

    # ------------------------------------------------------------------
    # TrackedTransaction
    # ------------------------------------------------------------------

    async def create_transaction(self, tx: TrackedTransaction) -> TrackedTransaction:
        """Persist a new tracked transaction."""
        async with self._ds.session() as session:
            session.add(tx)
            await session.commit()
            await session.refresh(tx)
        return tx

    async def get_transaction(self, tx_id: str) -> TrackedTransaction | None:
        """Find a tracked transaction by txid."""
        async with self._ds.session() as session:
            return await session.get(TrackedTransaction, tx_id)

    async def list_transactions(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> list[TrackedTransaction]:
        """List tracked transactions with optional status filter."""
        async with self._ds.session() as session:
            stmt = select(TrackedTransaction).order_by(TrackedTransaction.created_at.desc())
            if status:
                stmt = stmt.where(TrackedTransaction.tx_status == status)
            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_transaction(self, tx_id: str, **values: Any) -> bool:
        """Update fields on a tracked transaction."""
        async with self._ds.session() as session:
            stmt = update(TrackedTransaction).where(TrackedTransaction.id == tx_id).values(**values)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # TxInput
    # ------------------------------------------------------------------

    async def create_tx_inputs(self, inputs: list[TxInput]) -> None:
        """Bulk-create transaction input references."""
        if not inputs:
            return
        async with self._ds.session() as session:
            session.add_all(inputs)
            await session.commit()

    async def get_tx_inputs(self, tx_id: str) -> list[TxInput]:
        """Get all source input references for a transaction."""
        async with self._ds.session() as session:
            stmt = select(TxInput).where(TxInput.tx_id == tx_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ------------------------------------------------------------------
    # UserUTXO
    # ------------------------------------------------------------------

    async def create_utxo(self, utxo: UserUTXO) -> UserUTXO:
        """Persist a new user UTXO."""
        async with self._ds.session() as session:
            session.add(utxo)
            await session.commit()
            await session.refresh(utxo)
        return utxo

    async def create_utxos(self, utxos: list[UserUTXO]) -> None:
        """Bulk-create user UTXOs."""
        if not utxos:
            return
        async with self._ds.session() as session:
            session.add_all(utxos)
            await session.commit()

    async def get_utxos_for_user(
        self,
        user_id: str,
        *,
        bucket: str = "bsv",
        page: int = 1,
        page_size: int = 50,
    ) -> list[UserUTXO]:
        """List UTXOs for a user, optionally filtered by bucket."""
        async with self._ds.session() as session:
            stmt = (
                select(UserUTXO)
                .where(UserUTXO.user_id == user_id, UserUTXO.bucket == bucket)
                .order_by(UserUTXO.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_utxos_for_selection(
        self,
        user_id: str,
        *,
        bucket: str = "bsv",
        limit: int = 100,
    ) -> list[UserUTXO]:
        """Get UTXOs ordered for coin selection (oldest touched_at first)."""
        async with self._ds.session() as session:
            stmt = (
                select(UserUTXO)
                .where(UserUTXO.user_id == user_id, UserUTXO.bucket == bucket)
                .order_by(UserUTXO.touched_at.asc(), UserUTXO.created_at.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def delete_utxo(self, user_id: str, tx_id: str, vout: int) -> bool:
        """Delete a spent UTXO."""
        from sqlalchemy import delete as sa_delete

        async with self._ds.session() as session:
            stmt = sa_delete(UserUTXO).where(
                UserUTXO.user_id == user_id,
                UserUTXO.tx_id == tx_id,
                UserUTXO.vout == vout,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0  # type: ignore[union-attr]

    async def get_balance(self, user_id: str, *, bucket: str = "bsv") -> int:
        """Get total balance for a user in a bucket."""
        from sqlalchemy import func

        async with self._ds.session() as session:
            stmt = select(func.coalesce(func.sum(UserUTXO.satoshis), 0)).where(
                UserUTXO.user_id == user_id,
                UserUTXO.bucket == bucket,
            )
            result = await session.execute(stmt)
            return int(result.scalar_one())

    # ------------------------------------------------------------------
    # DataV2
    # ------------------------------------------------------------------

    async def create_data(self, data_records: list[DataV2]) -> None:
        """Bulk-create OP_RETURN data records."""
        if not data_records:
            return
        async with self._ds.session() as session:
            session.add_all(data_records)
            await session.commit()

    async def get_data_for_tx(self, tx_id: str) -> list[DataV2]:
        """Get all data outputs for a transaction."""
        async with self._ds.session() as session:
            stmt = select(DataV2).where(DataV2.tx_id == tx_id).order_by(DataV2.vout)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_data_for_user(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[DataV2]:
        """List data records for a user."""
        async with self._ds.session() as session:
            stmt = (
                select(DataV2)
                .where(DataV2.user_id == user_id)
                .order_by(DataV2.tx_id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
