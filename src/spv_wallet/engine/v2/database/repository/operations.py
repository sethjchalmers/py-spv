"""V2 operations repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from spv_wallet.engine.v2.database.models import Operation

if TYPE_CHECKING:
    from spv_wallet.datastore.client import Datastore


class OperationRepository:
    """Data access layer for V2 user operations."""

    def __init__(self, datastore: Datastore) -> None:
        self._ds = datastore

    async def create(self, operation: Operation) -> Operation:
        """Persist a new operation."""
        async with self._ds.session() as session:
            session.add(operation)
            await session.commit()
            await session.refresh(operation)
        return operation

    async def create_many(self, operations: list[Operation]) -> None:
        """Bulk-create operations."""
        if not operations:
            return
        async with self._ds.session() as session:
            session.add_all(operations)
            await session.commit()

    async def get(self, tx_id: str, user_id: str) -> Operation | None:
        """Find an operation by composite key (tx_id, user_id)."""
        async with self._ds.session() as session:
            return await session.get(Operation, (tx_id, user_id))

    async def list_by_user(
        self,
        user_id: str,
        *,
        op_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[Operation]:
        """List operations for a user with optional type filter."""
        async with self._ds.session() as session:
            stmt = select(Operation).where(Operation.user_id == user_id)
            if op_type:
                stmt = stmt.where(Operation.type == op_type)
            stmt = (
                stmt.order_by(Operation.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_by_tx(self, tx_id: str) -> list[Operation]:
        """List all operations for a transaction."""
        async with self._ds.session() as session:
            stmt = select(Operation).where(Operation.tx_id == tx_id)
            result = await session.execute(stmt)
            return list(result.scalars().all())
