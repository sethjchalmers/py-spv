"""V2 users repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from spv_wallet.engine.v2.database.models import UserV2

if TYPE_CHECKING:
    from spv_wallet.datastore.client import Datastore


class UserRepository:
    """Data access layer for V2 users."""

    def __init__(self, datastore: Datastore) -> None:
        self._ds = datastore

    async def create(self, user: UserV2) -> UserV2:
        """Persist a new user."""
        async with self._ds.session() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

    async def get_by_id(self, user_id: str) -> UserV2 | None:
        """Find user by primary key (compressed pubkey ID)."""
        async with self._ds.session() as session:
            return await session.get(UserV2, user_id)

    async def get_by_pub_key(self, pub_key: str) -> UserV2 | None:
        """Find user by hex-encoded public key."""
        async with self._ds.session() as session:
            stmt = select(UserV2).where(UserV2.pub_key == pub_key)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_all(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[UserV2]:
        """List users with pagination."""
        async with self._ds.session() as session:
            stmt = (
                select(UserV2)
                .order_by(UserV2.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def delete_by_id(self, user_id: str) -> bool:
        """Delete a user by ID. Returns True if deleted."""
        async with self._ds.session() as session:
            stmt = delete(UserV2).where(UserV2.id == user_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0  # type: ignore[union-attr]
