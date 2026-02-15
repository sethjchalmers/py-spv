"""V2 paymails service implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from spv_wallet.engine.v2.database.models import PaymailV2
from spv_wallet.engine.v2.database.repository.paymails import PaymailRepository
from spv_wallet.errors.definitions import (
    ErrInvalidPaymail,
    ErrPaymailDuplicate,
    ErrPaymailNotFound,
    ErrUserNotFound,
)

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class PaymailsServiceV2:
    """V2 paymail management — create, list, delete paymails for users."""

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine
        self._repo = PaymailRepository(engine.datastore)

    async def create_paymail(
        self,
        user_id: str,
        alias: str,
        domain: str,
        *,
        public_name: str = "",
        avatar: str = "",
    ) -> PaymailV2:
        """Create a paymail for a user.

        Args:
            user_id: The V2 user ID.
            alias: Paymail alias (local part).
            domain: Paymail domain.
            public_name: Optional display name.
            avatar: Optional avatar URL.

        Returns:
            The persisted PaymailV2 model.

        Raises:
            SPVError: If user not found, paymail invalid, or duplicate.
        """
        if not alias or not domain:
            raise ErrInvalidPaymail

        # Validate user exists via users service
        from spv_wallet.engine.v2.database.repository.users import UserRepository

        user_repo = UserRepository(self._engine.datastore)
        user = await user_repo.get_by_id(user_id)
        if user is None:
            raise ErrUserNotFound

        # Check for duplicates
        existing = await self._repo.get_by_alias_domain(alias, domain)
        if existing is not None:
            raise ErrPaymailDuplicate

        paymail = PaymailV2(
            alias=alias,
            domain=domain,
            public_name=public_name,
            avatar=avatar,
            user_id=user_id,
        )
        return await self._repo.create(paymail)

    async def get_paymail(self, paymail_id: int) -> PaymailV2:
        """Get a paymail by ID.

        Raises:
            SPVError: If not found.
        """
        paymail = await self._repo.get_by_id(paymail_id)
        if paymail is None or paymail.deleted_at is not None:
            raise ErrPaymailNotFound
        return paymail

    async def get_by_address(self, alias: str, domain: str) -> PaymailV2 | None:
        """Get a paymail by alias@domain. Returns None if not found."""
        return await self._repo.get_by_alias_domain(alias, domain)

    async def list_for_user(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> list[PaymailV2]:
        """List paymails for a user."""
        return await self._repo.list_by_user(user_id, page=page, page_size=page_size)

    async def list_all(self, *, page: int = 1, page_size: int = 50) -> list[PaymailV2]:
        """List all paymails (admin)."""
        return await self._repo.list_all(page=page, page_size=page_size)

    async def delete_paymail(self, paymail_id: int) -> None:
        """Soft-delete a paymail.

        Raises:
            SPVError: If not found.
        """
        deleted = await self._repo.soft_delete(paymail_id)
        if not deleted:
            raise ErrPaymailNotFound
