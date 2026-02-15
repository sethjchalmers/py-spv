"""V2 users service implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from spv_wallet.engine.v2.database.models import UserV2
from spv_wallet.engine.v2.database.repository.users import UserRepository
from spv_wallet.errors.definitions import (
    ErrInvalidPubKey,
    ErrMissingFieldPubKey,
    ErrUserAlreadyExists,
    ErrUserNotFound,
)

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class UsersService:
    """V2 user management — create, get, delete users.

    Users are identified by compressed public key. The user ID is derived
    from the public key (Base58Check encoding of the key hash).
    """

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine
        self._repo = UserRepository(engine.datastore)

    async def create_user(self, pub_key: str) -> UserV2:
        """Create a new V2 user from a public key.

        Args:
            pub_key: Hex-encoded compressed public key (66 chars).

        Returns:
            The persisted UserV2 model.

        Raises:
            SPVError: If pub_key is missing, invalid, or already exists.
        """
        if not pub_key:
            raise ErrMissingFieldPubKey

        if len(pub_key) != 66 or pub_key[0:2] not in ("02", "03"):
            raise ErrInvalidPubKey

        # Derive user ID from public key (address-style hash)
        user_id = self._derive_user_id(pub_key)

        # Check if user already exists
        existing = await self._repo.get_by_id(user_id)
        if existing is not None:
            raise ErrUserAlreadyExists

        user = UserV2(id=user_id, pub_key=pub_key)
        return await self._repo.create(user)

    async def get_user(self, user_id: str) -> UserV2:
        """Get a user by ID.

        Raises:
            SPVError: If user not found.
        """
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise ErrUserNotFound
        return user

    async def get_user_by_pub_key(self, pub_key: str) -> UserV2 | None:
        """Get a user by public key. Returns None if not found."""
        return await self._repo.get_by_pub_key(pub_key)

    async def list_users(self, *, page: int = 1, page_size: int = 50) -> list[UserV2]:
        """List all users with pagination."""
        return await self._repo.list_all(page=page, page_size=page_size)

    async def delete_user(self, user_id: str) -> None:
        """Delete a user and all associated data.

        Raises:
            SPVError: If user not found.
        """
        deleted = await self._repo.delete_by_id(user_id)
        if not deleted:
            raise ErrUserNotFound

    @staticmethod
    def _derive_user_id(pub_key: str) -> str:
        """Derive a 34-char user ID from a compressed public key.

        Uses RIPEMD160(SHA256(pubkey)) → Base58Check encoding,
        same as a Bitcoin P2PKH address derivation.
        """
        from spv_wallet.bsv.address import pubkey_to_address

        return pubkey_to_address(bytes.fromhex(pub_key))
