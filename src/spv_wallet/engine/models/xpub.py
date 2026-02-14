"""Xpub model — extended public keys for user identification."""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, ModelOps, TimestampMixin


class Xpub(Base, TimestampMixin, MetadataMixin, ModelOps):
    """Extended public key — primary user identity in V1.

    Tracks the xPub's balance and BIP32 derivation counters.
    """

    __tablename__ = "xpubs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="SHA-256 hash of the xPub string (xPubID)"
    )
    current_balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    next_internal_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_external_num: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Xpub id={self.id[:16]}... balance={self.current_balance}>"
