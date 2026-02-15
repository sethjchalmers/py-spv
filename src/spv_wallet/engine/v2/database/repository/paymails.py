"""V2 paymails repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from spv_wallet.engine.v2.database.models import PaymailV2

if TYPE_CHECKING:
    from spv_wallet.datastore.client import Datastore


class PaymailRepository:
    """Data access layer for V2 paymail addresses."""

    def __init__(self, datastore: Datastore) -> None:
        self._ds = datastore

    async def create(self, paymail: PaymailV2) -> PaymailV2:
        """Persist a new paymail address."""
        async with self._ds.session() as session:
            session.add(paymail)
            await session.commit()
            await session.refresh(paymail)
        return paymail

    async def get_by_id(self, paymail_id: int) -> PaymailV2 | None:
        """Find paymail by primary key."""
        async with self._ds.session() as session:
            return await session.get(PaymailV2, paymail_id)

    async def get_by_alias_domain(self, alias: str, domain: str) -> PaymailV2 | None:
        """Find paymail by alias + domain combination."""
        async with self._ds.session() as session:
            stmt = select(PaymailV2).where(
                PaymailV2.alias == alias,
                PaymailV2.domain == domain,
                PaymailV2.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[PaymailV2]:
        """List paymails for a user with pagination."""
        async with self._ds.session() as session:
            stmt = (
                select(PaymailV2)
                .where(PaymailV2.user_id == user_id, PaymailV2.deleted_at.is_(None))
                .order_by(PaymailV2.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def list_all(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[PaymailV2]:
        """List all paymails with pagination."""
        async with self._ds.session() as session:
            stmt = (
                select(PaymailV2)
                .where(PaymailV2.deleted_at.is_(None))
                .order_by(PaymailV2.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def soft_delete(self, paymail_id: int) -> bool:
        """Soft-delete a paymail by setting deleted_at."""
        from datetime import UTC, datetime

        async with self._ds.session() as session:
            stmt = (
                update(PaymailV2)
                .where(PaymailV2.id == paymail_id, PaymailV2.deleted_at.is_(None))
                .values(deleted_at=datetime.now(UTC))
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0  # type: ignore[union-attr]
