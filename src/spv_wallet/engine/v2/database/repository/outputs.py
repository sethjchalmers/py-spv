"""V2 outputs repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from spv_wallet.engine.v2.database.models import TrackedOutput

if TYPE_CHECKING:
    from spv_wallet.datastore.client import Datastore


class OutputRepository:
    """Data access layer for V2 tracked outputs."""

    def __init__(self, datastore: Datastore) -> None:
        self._ds = datastore

    async def create(self, output: TrackedOutput) -> TrackedOutput:
        """Persist a new tracked output."""
        async with self._ds.session() as session:
            session.add(output)
            await session.commit()
            await session.refresh(output)
        return output

    async def create_many(self, outputs: list[TrackedOutput]) -> None:
        """Bulk-create tracked outputs."""
        if not outputs:
            return
        async with self._ds.session() as session:
            session.add_all(outputs)
            await session.commit()

    async def get(self, tx_id: str, vout: int) -> TrackedOutput | None:
        """Find a tracked output by (tx_id, vout) composite key."""
        async with self._ds.session() as session:
            return await session.get(TrackedOutput, (tx_id, vout))

    async def list_by_tx(self, tx_id: str) -> list[TrackedOutput]:
        """Get all outputs for a transaction."""
        async with self._ds.session() as session:
            stmt = (
                select(TrackedOutput)
                .where(TrackedOutput.tx_id == tx_id)
                .order_by(TrackedOutput.vout)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_by_user(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[TrackedOutput]:
        """List outputs owned by a user."""
        async with self._ds.session() as session:
            stmt = (
                select(TrackedOutput)
                .where(TrackedOutput.user_id == user_id)
                .order_by(TrackedOutput.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_unspent_by_user(self, user_id: str) -> list[TrackedOutput]:
        """List unspent outputs for a user."""
        async with self._ds.session() as session:
            stmt = (
                select(TrackedOutput)
                .where(
                    TrackedOutput.user_id == user_id,
                    TrackedOutput.spending_tx == "",
                )
                .order_by(TrackedOutput.created_at.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def mark_spent(self, tx_id: str, vout: int, spending_tx_id: str) -> bool:
        """Mark an output as spent by setting spending_tx."""
        async with self._ds.session() as session:
            stmt = (
                update(TrackedOutput)
                .where(
                    TrackedOutput.tx_id == tx_id,
                    TrackedOutput.vout == vout,
                    TrackedOutput.spending_tx == "",
                )
                .values(spending_tx=spending_tx_id)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0  # type: ignore[union-attr]
