"""Contact model — paymail-based contacts."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, TimestampMixin


class Contact(Base, TimestampMixin, MetadataMixin):
    """A paymail-based contact with confirmation/trust status.

    Contacts are discovered and exchanged via the PIKE protocol.
    """

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="Unique contact ID"
    )
    xpub_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Owning xPub ID"
    )
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="", comment="Contact display name"
    )
    paymail: Mapped[str] = mapped_column(
        String(320), nullable=False, index=True, comment="Contact's paymail address"
    )
    pub_key: Mapped[str] = mapped_column(
        String(130), nullable=False, default="", comment="Contact's public key hex"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unconfirmed",
        comment="unconfirmed | awaiting | confirmed | rejected",
    )

    def __repr__(self) -> str:
        return f"<Contact paymail={self.paymail} status={self.status}>"
