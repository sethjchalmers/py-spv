"""Contact service — paymail-based contact management.

Mirrors the Go engine contact.go service:
- Create / upsert contacts (discovered via PIKE)
- Update contact status (unconfirmed → awaiting → confirmed | rejected)
- Search / list contacts
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from spv_wallet.engine.models.contact import Contact
from spv_wallet.errors.definitions import (
    ErrContactDuplicate,
    ErrContactInvalidStatus,
    ErrContactNotFound,
)

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine

# Valid status values
CONTACT_STATUS_UNCONFIRMED = "unconfirmed"
CONTACT_STATUS_AWAITING = "awaiting"
CONTACT_STATUS_CONFIRMED = "confirmed"
CONTACT_STATUS_REJECTED = "rejected"

_VALID_STATUSES = {
    CONTACT_STATUS_UNCONFIRMED,
    CONTACT_STATUS_AWAITING,
    CONTACT_STATUS_CONFIRMED,
    CONTACT_STATUS_REJECTED,
}

# Allowed status transitions
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    CONTACT_STATUS_UNCONFIRMED: {CONTACT_STATUS_AWAITING, CONTACT_STATUS_REJECTED},
    CONTACT_STATUS_AWAITING: {CONTACT_STATUS_CONFIRMED, CONTACT_STATUS_REJECTED},
    CONTACT_STATUS_CONFIRMED: {CONTACT_STATUS_REJECTED},
    CONTACT_STATUS_REJECTED: set(),
}


class ContactService:
    """Business logic for paymail-based contact management.

    Contacts are created during PIKE exchanges and track the trust
    status between two paymail users.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_contact(
        self,
        xpub_id: str,
        paymail: str,
        *,
        full_name: str = "",
        pub_key: str = "",
        status: str = CONTACT_STATUS_UNCONFIRMED,
        metadata: dict[str, Any] | None = None,
    ) -> Contact:
        """Create a new contact.

        Args:
            xpub_id: The owning xPub ID.
            paymail: The contact's paymail address.
            full_name: The contact's display name.
            pub_key: The contact's public key hex.
            status: Initial status (default: unconfirmed).
            metadata: Optional metadata.

        Returns:
            The persisted Contact model.

        Raises:
            SPVError: If duplicate or invalid status.
        """
        if status not in _VALID_STATUSES:
            raise ErrContactInvalidStatus

        # Check for existing contact with same xpub_id + paymail
        existing = await self.get_contact_by_paymail(xpub_id, paymail)
        if existing is not None:
            raise ErrContactDuplicate

        contact = Contact(
            id=uuid.uuid4().hex,
            xpub_id=xpub_id,
            full_name=full_name,
            paymail=paymail,
            pub_key=pub_key,
            status=status,
        )
        if metadata:
            contact.metadata_ = metadata

        async with self._engine.datastore.session() as session:
            session.add(contact)
            await session.commit()
            await session.refresh(contact)

        return contact

    async def upsert_contact(
        self,
        xpub_id: str,
        paymail: str,
        *,
        full_name: str = "",
        pub_key: str = "",
        status: str = CONTACT_STATUS_UNCONFIRMED,
    ) -> Contact:
        """Create or update a contact (used by PIKE).

        If the contact already exists, update its name, key, and status.

        Args:
            xpub_id: The owning xPub ID.
            paymail: The contact's paymail address.
            full_name: The contact's display name.
            pub_key: The contact's public key hex.
            status: Desired status.

        Returns:
            The Contact model (created or updated).
        """
        existing = await self.get_contact_by_paymail(xpub_id, paymail)
        if existing is not None:
            # Update existing
            async with self._engine.datastore.session() as session:
                result = await session.execute(select(Contact).where(Contact.id == existing.id))
                contact = result.scalar_one()
                if full_name:
                    contact.full_name = full_name
                if pub_key:
                    contact.pub_key = pub_key
                contact.status = status
                await session.commit()
                await session.refresh(contact)
                return contact

        return await self.create_contact(
            xpub_id,
            paymail,
            full_name=full_name,
            pub_key=pub_key,
            status=status,
        )

    async def update_status(self, contact_id: str, new_status: str) -> Contact:
        """Transition a contact's status.

        Enforces valid status transitions:
        - unconfirmed → awaiting | rejected
        - awaiting → confirmed | rejected
        - confirmed → rejected
        - rejected → (terminal)

        Args:
            contact_id: The contact ID.
            new_status: The target status.

        Returns:
            The updated Contact model.

        Raises:
            SPVError: If contact not found or transition invalid.
        """
        if new_status not in _VALID_STATUSES:
            raise ErrContactInvalidStatus

        async with self._engine.datastore.session() as session:
            result = await session.execute(select(Contact).where(Contact.id == contact_id))
            contact = result.scalar_one_or_none()
            if contact is None:
                raise ErrContactNotFound

            allowed = _STATUS_TRANSITIONS.get(contact.status, set())
            if new_status not in allowed:
                raise ErrContactInvalidStatus

            contact.status = new_status
            await session.commit()
            await session.refresh(contact)
            return contact

    async def delete_contact(self, contact_id: str) -> None:
        """Delete a contact by ID.

        Args:
            contact_id: The contact ID.

        Raises:
            SPVError: If not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(delete(Contact).where(Contact.id == contact_id))
            await session.commit()

        if result.rowcount == 0:  # type: ignore[union-attr]
            raise ErrContactNotFound

    async def get_contact(self, contact_id: str) -> Contact | None:
        """Get a contact by ID.

        Args:
            contact_id: The contact ID.

        Returns:
            The Contact, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(select(Contact).where(Contact.id == contact_id))
            return result.scalar_one_or_none()

    async def get_contact_by_paymail(self, xpub_id: str, paymail: str) -> Contact | None:
        """Look up a contact by owning xPub and paymail.

        Args:
            xpub_id: The owning xPub ID.
            paymail: The contact's paymail address.

        Returns:
            The Contact, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Contact).where(
                    Contact.xpub_id == xpub_id,
                    Contact.paymail == paymail,
                )
            )
            return result.scalar_one_or_none()

    async def search_contacts(
        self,
        *,
        xpub_id: str | None = None,
        status: str | None = None,
        paymail: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Contact]:
        """Search contacts with optional filters.

        Args:
            xpub_id: Filter by owning xPub ID.
            status: Filter by status.
            paymail: Filter by paymail (exact).
            limit: Maximum results.
            offset: Skip count.

        Returns:
            List of matching Contact records.
        """
        stmt = select(Contact)
        if xpub_id:
            stmt = stmt.where(Contact.xpub_id == xpub_id)
        if status:
            stmt = stmt.where(Contact.status == status)
        if paymail:
            stmt = stmt.where(Contact.paymail == paymail)
        stmt = stmt.limit(limit).offset(offset)

        async with self._engine.datastore.session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())
