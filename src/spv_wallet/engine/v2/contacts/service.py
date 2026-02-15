"""V2 contacts service implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

from spv_wallet.engine.v2.database.models import ContactStatus, UserContact
from spv_wallet.errors.definitions import (
    ErrContactDuplicate,
    ErrContactInvalidStatus,
    ErrContactNotFound,
)

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


# Valid status transitions
_VALID_TRANSITIONS: dict[str, set[str]] = {
    ContactStatus.UNCONFIRMED.value: {ContactStatus.AWAITING.value, ContactStatus.REJECTED.value},
    ContactStatus.AWAITING.value: {ContactStatus.CONFIRMED.value, ContactStatus.REJECTED.value},
    ContactStatus.CONFIRMED.value: {ContactStatus.REJECTED.value},
    ContactStatus.REJECTED.value: set(),
}


class ContactsServiceV2:
    """V2 contact management — create, list, update status, delete contacts."""

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    async def create_contact(
        self,
        user_id: str,
        *,
        full_name: str,
        paymail: str = "",
        pub_key: str = "",
    ) -> UserContact:
        """Create a new contact for a user.

        Args:
            user_id: The V2 user ID.
            full_name: Contact display name.
            paymail: Contact's paymail address.
            pub_key: Contact's public key.

        Returns:
            The persisted UserContact model.

        Raises:
            SPVError: If a contact with the same paymail already exists for this user.
        """
        # Check for duplicate (same user + paymail)
        if paymail:
            existing = await self._find_by_paymail(user_id, paymail)
            if existing is not None:
                raise ErrContactDuplicate

        contact = UserContact(
            full_name=full_name,
            paymail=paymail,
            pub_key=pub_key,
            user_id=user_id,
            status=ContactStatus.UNCONFIRMED.value,
        )

        async with self._engine.datastore.session() as session:
            session.add(contact)
            await session.commit()
            await session.refresh(contact)
        return contact

    async def get_contact(self, contact_id: int) -> UserContact:
        """Get a contact by ID.

        Raises:
            SPVError: If not found.
        """
        async with self._engine.datastore.session() as session:
            contact = await session.get(UserContact, contact_id)
        if contact is None or contact.deleted_at is not None:
            raise ErrContactNotFound
        return contact

    async def list_for_user(
        self,
        user_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[UserContact]:
        """List contacts for a user."""
        async with self._engine.datastore.session() as session:
            stmt = select(UserContact).where(
                UserContact.user_id == user_id,
                UserContact.deleted_at.is_(None),
            )
            if status:
                stmt = stmt.where(UserContact.status == status)
            stmt = (
                stmt.order_by(UserContact.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def update_status(self, contact_id: int, new_status: str) -> UserContact:
        """Update a contact's status.

        Args:
            contact_id: The contact ID.
            new_status: The new status value.

        Returns:
            The updated contact.

        Raises:
            SPVError: If contact not found or invalid status transition.
        """
        contact = await self.get_contact(contact_id)

        valid_next = _VALID_TRANSITIONS.get(contact.status, set())
        if new_status not in valid_next:
            raise ErrContactInvalidStatus

        async with self._engine.datastore.session() as session:
            stmt = update(UserContact).where(UserContact.id == contact_id).values(status=new_status)
            await session.execute(stmt)
            await session.commit()

        # Return fresh copy
        return await self.get_contact(contact_id)

    async def delete_contact(self, contact_id: int) -> None:
        """Soft-delete a contact.

        Raises:
            SPVError: If not found.
        """
        from datetime import UTC, datetime

        await self.get_contact(contact_id)  # validates existence

        async with self._engine.datastore.session() as session:
            stmt = (
                update(UserContact)
                .where(UserContact.id == contact_id, UserContact.deleted_at.is_(None))
                .values(deleted_at=datetime.now(UTC))
            )
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount == 0:  # type: ignore[union-attr]
                raise ErrContactNotFound

    async def _find_by_paymail(self, user_id: str, paymail: str) -> UserContact | None:
        """Find an active contact by user + paymail."""
        async with self._engine.datastore.session() as session:
            stmt = select(UserContact).where(
                UserContact.user_id == user_id,
                UserContact.paymail == paymail,
                UserContact.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
