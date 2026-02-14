"""XPub service — registration and derivation."""

from __future__ import annotations

import json
from datetime import UTC
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from spv_wallet.bsv.keys import ExtendedKey, xpub_id
from spv_wallet.engine.models.xpub import Xpub
from spv_wallet.errors.definitions import ErrInvalidXPub, ErrMissingFieldXPub, ErrXPubNotFound

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine


class XPubService:
    """Business logic for xPub registration, lookup, and management.

    Mirrors the Go engine xpub.go service:
    - Validate xPub (BIP32 deserialization)
    - Hash to xPubID (SHA-256)
    - Cache xPub lookups
    - Track derivation counters (next_internal_num, next_external_num)
    """

    CACHE_KEY_PREFIX = "xpub:"

    def __init__(self, engine: SPVWalletEngine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def new_xpub(
        self,
        raw_xpub: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> Xpub:
        """Register a new xPub.

        Args:
            raw_xpub: The Base58Check xpub string.
            metadata: Optional metadata to attach.

        Returns:
            The persisted Xpub model.

        Raises:
            SPVError: If xPub is missing or invalid, or already exists.
        """
        if not raw_xpub:
            raise ErrMissingFieldXPub

        # Validate via BIP32 deserialization
        try:
            key = ExtendedKey.from_string(raw_xpub)
        except ValueError as exc:
            raise ErrInvalidXPub from exc

        if key.is_private:
            raise ErrInvalidXPub

        xpub_hash = xpub_id(raw_xpub)

        # Check if already exists
        existing = await self.get_xpub_by_id(xpub_hash)
        if existing is not None:
            return existing

        xpub = Xpub(
            id=xpub_hash,
            current_balance=0,
            next_internal_num=0,
            next_external_num=0,
        )
        if metadata:
            xpub.metadata_ = metadata

        async with self._engine.datastore.session() as session:
            session.add(xpub)
            await session.commit()
            await session.refresh(xpub)

        # Cache
        await self._cache_xpub(xpub)

        return xpub

    async def get_xpub(self, raw_xpub: str) -> Xpub:
        """Look up an xPub by its raw string.

        Args:
            raw_xpub: The Base58Check xpub string.

        Returns:
            The Xpub model.

        Raises:
            SPVError: If not found.
        """
        xpub_hash = xpub_id(raw_xpub)
        return await self.get_xpub_by_id(xpub_hash, required=True)  # type: ignore[return-value]

    async def get_xpub_by_id(self, id_: str, *, required: bool = False) -> Xpub | None:
        """Look up an xPub by its hashed ID.

        Args:
            id_: The 64-char hex xPubID (SHA-256 hash).
            required: If True, raise ErrXPubNotFound when missing.

        Returns:
            The Xpub model, or None if not found and not required.
        """
        # Try cache first
        cached = await self._engine.cache.get(f"{self.CACHE_KEY_PREFIX}{id_}")
        if cached is not None:
            return self._deserialize_from_cache(cached)

        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Xpub).where(Xpub.id == id_, Xpub.deleted_at.is_(None))
            )
            xpub = result.scalar_one_or_none()

        if xpub is None:
            if required:
                raise ErrXPubNotFound
            return None

        # Populate cache
        await self._cache_xpub(xpub)

        return xpub

    async def update_metadata(self, id_: str, metadata: dict[str, Any]) -> Xpub:
        """Merge metadata onto an existing xPub.

        Args:
            id_: The xPubID.
            metadata: Key-value pairs to merge into existing metadata.

        Returns:
            The updated Xpub model.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Xpub).where(Xpub.id == id_, Xpub.deleted_at.is_(None))
            )
            xpub = result.scalar_one_or_none()
            if xpub is None:
                raise ErrXPubNotFound

            existing = dict(xpub.metadata_ or {})
            existing.update(metadata)
            xpub.metadata_ = existing  # Assign new dict to trigger change detection

            await session.commit()
            await session.refresh(xpub)

        # Invalidate cache
        await self._invalidate_cache(id_)

        return xpub

    async def delete_xpub(self, id_: str) -> None:
        """Soft-delete an xPub by setting deleted_at.

        Args:
            id_: The xPubID.
        """
        from datetime import datetime

        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Xpub).where(Xpub.id == id_, Xpub.deleted_at.is_(None))
            )
            xpub = result.scalar_one_or_none()
            if xpub is None:
                raise ErrXPubNotFound

            xpub.deleted_at = datetime.now(UTC)
            await session.commit()

        # Invalidate cache
        await self._invalidate_cache(id_)

    async def increment_chain(self, id_: str, *, chain: int, count: int = 1) -> int:
        """Increment the next derivation number for a chain and return the starting index.

        Args:
            id_: The xPubID.
            chain: 0 = external, 1 = internal.
            count: How many indices to reserve (default 1).

        Returns:
            The starting index that was reserved.
        """
        async with self._engine.datastore.session() as session:
            result = await session.execute(
                select(Xpub).where(Xpub.id == id_, Xpub.deleted_at.is_(None))
            )
            xpub = result.scalar_one_or_none()
            if xpub is None:
                raise ErrXPubNotFound

            if chain == 0:
                start = xpub.next_external_num
                xpub.next_external_num = start + count
            else:
                start = xpub.next_internal_num
                xpub.next_internal_num = start + count

            await session.commit()

        # Invalidate cache (counters changed)
        await self._invalidate_cache(id_)

        return start

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _cache_xpub(self, xpub: Xpub) -> None:
        """Store xPub in cache."""
        data = {
            "id": xpub.id,
            "current_balance": xpub.current_balance,
            "next_internal_num": xpub.next_internal_num,
            "next_external_num": xpub.next_external_num,
        }
        ttl = self._engine.config.cache.ttl_seconds
        await self._engine.cache.set(
            f"{self.CACHE_KEY_PREFIX}{xpub.id}",
            json.dumps(data),
            ttl=ttl,
        )

    async def _invalidate_cache(self, id_: str) -> None:
        """Remove xPub from cache."""
        await self._engine.cache.delete(f"{self.CACHE_KEY_PREFIX}{id_}")

    def _deserialize_from_cache(self, raw: str) -> Xpub:
        """Reconstruct a minimal Xpub from cached JSON."""
        data = json.loads(raw)
        return Xpub(
            id=data["id"],
            current_balance=data["current_balance"],
            next_internal_num=data["next_internal_num"],
            next_external_num=data["next_external_num"],
        )
