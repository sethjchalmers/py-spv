"""V2 addresses repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from spv_wallet.engine.v2.database.models import AddressV2

if TYPE_CHECKING:
    from spv_wallet.datastore.client import Datastore


class AddressRepository:
    """Data access layer for V2 bitcoin addresses."""

    def __init__(self, datastore: Datastore) -> None:
        self._ds = datastore

    async def create(self, address: AddressV2) -> AddressV2:
        """Persist a new address."""
        async with self._ds.session() as session:
            session.add(address)
            await session.commit()
            await session.refresh(address)
        return address

    async def get_by_address(self, address: str) -> AddressV2 | None:
        """Find address by primary key (Base58Check address)."""
        async with self._ds.session() as session:
            result = await session.get(AddressV2, address)
            if result and result.deleted_at is not None:
                return None
            return result

    async def list_by_user(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[AddressV2]:
        """List addresses for a user with pagination."""
        async with self._ds.session() as session:
            stmt = (
                select(AddressV2)
                .where(AddressV2.user_id == user_id, AddressV2.deleted_at.is_(None))
                .order_by(AddressV2.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def soft_delete(self, address: str) -> bool:
        """Soft-delete an address by setting deleted_at."""
        from datetime import UTC, datetime

        async with self._ds.session() as session:
            stmt = (
                update(AddressV2)
                .where(AddressV2.address == address, AddressV2.deleted_at.is_(None))
                .values(deleted_at=datetime.now(UTC))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0  # type: ignore[union-attr]
