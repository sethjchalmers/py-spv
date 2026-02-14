"""PaymailAddress model — paymail handles linked to xPubs."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, ModelOps, TimestampMixin


class PaymailAddress(Base, TimestampMixin, MetadataMixin, ModelOps):
    """A paymail handle (``alias@domain``) linked to an xPub.

    Paymail addresses are the human-readable identifiers used
    for receiving payments via the paymail protocol.
    """

    __tablename__ = "paymail_addresses"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="SHA-256 hash of alias@domain"
    )
    xpub_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Owning xPub ID"
    )
    alias: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Paymail alias (local part)"
    )
    domain: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Paymail domain"
    )
    public_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="Display name"
    )
    avatar: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="Avatar URL"
    )

    @property
    def address(self) -> str:
        """Return the full paymail address (alias@domain)."""
        return f"{self.alias}@{self.domain}"

    def __repr__(self) -> str:
        return f"<PaymailAddress {self.alias}@{self.domain}>"
