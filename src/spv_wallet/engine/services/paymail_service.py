"""PaymailAddress service — CRUD operations for paymail handles.

Mirrors the Go engine paymail_address.go service:
- Create paymail address (alias@domain) linked to an xPub
- Delete paymail address
- Search / list paymail addresses
- Resolve alias@domain to an xPub
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, select

from spv_wallet.engine.models.paymail_address import PaymailAddress
from spv_wallet.errors.definitions import (
    ErrPaymailDomainNotAllowed,
    ErrPaymailDuplicate,
    ErrPaymailNotFound,
)
from spv_wallet.paymail.models import SanitizedPaymail
from spv_wallet.utils.crypto import sha256

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class PaymailService:
    """Business logic for paymail address management.

    Handles creation, deletion, lookup, and search of paymail
    addresses that are linked to registered xPubs.
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_paymail(
        self,
        xpub_id: str,
        address: str,
        *,
        public_name: str = "",
        avatar: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> PaymailAddress:
        """Create a new paymail address for an xPub.

        Args:
            xpub_id: The owning xPub ID (SHA-256 hash).
            address: The paymail address (e.g. ``user@example.com``).
            public_name: Optional display name.
            avatar: Optional avatar URL.
            metadata: Optional metadata to attach.

        Returns:
            The persisted PaymailAddress model.

        Raises:
            SPVError: If address is invalid, domain not allowed, or duplicate.
        """
        # Validate format
        sanitized = SanitizedPaymail.from_string(address)

        # Check domain is allowed
        self._validate_domain(sanitized.domain)

        # Generate deterministic ID
        paymail_id = sha256(sanitized.address.encode("utf-8")).hex()

        # Check for duplicates
        existing = await self.get_paymail_by_id(paymail_id)
        if existing is not None:
            raise ErrPaymailDuplicate

        paymail = PaymailAddress(
            id=paymail_id,
            xpub_id=xpub_id,
            alias=sanitized.alias,
            domain=sanitized.domain,
            public_name=public_name,
            avatar=avatar,
        )
        if metadata:
            paymail.metadata_ = metadata

        async with self._engine.datastore.session() as session:
            session.add(paymail)
            await session.commit()
            await session.refresh(paymail)

        return paymail

    async def delete_paymail(self, address: str) -> None:
        """Delete a paymail address.

        Args:
            address: The paymail address to delete (e.g. ``user@example.com``).

        Raises:
            SPVError: If not found.
        """
        sanitized = SanitizedPaymail.from_string(address)
        paymail_id = sha256(sanitized.address.encode("utf-8")).hex()

        async with self._engine.datastore.session() as session:
            result = await session.execute(
                delete(PaymailAddress).where(PaymailAddress.id == paymail_id)
            )
            await session.commit()

        if result.rowcount == 0:  # type: ignore[union-attr]
            raise ErrPaymailNotFound

    async def get_paymail_by_id(self, paymail_id: str) -> PaymailAddress | None:
        """Look up a paymail address by its ID.

        Args:
            paymail_id: The SHA-256 hash ID of the paymail address.

        Returns:
            The PaymailAddress, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(PaymailAddress).where(PaymailAddress.id == paymail_id)
            )
            return result.scalar_one_or_none()

    async def get_paymail_by_alias(self, alias: str, domain: str) -> PaymailAddress | None:
        """Look up a paymail address by alias and domain.

        Args:
            alias: The local part (before @).
            domain: The domain part (after @).

        Returns:
            The PaymailAddress, or None if not found.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(PaymailAddress).where(
                    PaymailAddress.alias == alias.lower(),
                    PaymailAddress.domain == domain.lower(),
                )
            )
            return result.scalar_one_or_none()

    async def get_paymails_by_xpub(self, xpub_id: str) -> list[PaymailAddress]:
        """List all paymail addresses owned by an xPub.

        Args:
            xpub_id: The owning xPub ID.

        Returns:
            List of PaymailAddress records.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(PaymailAddress).where(PaymailAddress.xpub_id == xpub_id)
            )
            return list(result.scalars().all())

    async def search_paymails(
        self,
        *,
        xpub_id: str | None = None,
        alias: str | None = None,
        domain: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PaymailAddress]:
        """Search paymail addresses with optional filters.

        Args:
            xpub_id: Filter by owning xPub ID.
            alias: Filter by alias (exact match).
            domain: Filter by domain (exact match).
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            List of matching PaymailAddress records.
        """
        stmt = select(PaymailAddress)
        if xpub_id:
            stmt = stmt.where(PaymailAddress.xpub_id == xpub_id)
        if alias:
            stmt = stmt.where(PaymailAddress.alias == alias.lower())
        if domain:
            stmt = stmt.where(PaymailAddress.domain == domain.lower())
        stmt = stmt.limit(limit).offset(offset)

        async with self._engine.datastore.session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_domain(self, domain: str) -> None:
        """Check that the domain is in the server's allowed list.

        If no domains are configured, all domains are allowed.

        Args:
            domain: The domain to validate.

        Raises:
            SPVError: If the domain is not allowed.
        """
        allowed = self._engine.config.paymail.domains
        if allowed and domain not in allowed:
            raise ErrPaymailDomainNotAllowed
