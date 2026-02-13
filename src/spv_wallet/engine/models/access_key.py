"""AccessKey model — ephemeral API authentication keys."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, TimestampMixin


class AccessKey(Base, TimestampMixin, MetadataMixin):
    """Ephemeral key pair for API authentication (alternative to full xPub auth).

    The ``key`` column stores the compressed public key hex, while the private
    key is returned only at creation and never stored.
    """

    __tablename__ = "access_keys"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="SHA-256 hash of the public key"
    )
    xpub_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Owning xPub ID"
    )
    key: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Compressed public key hex"
    )

    def __repr__(self) -> str:
        return f"<AccessKey id={self.id[:16]}... xpub={self.xpub_id[:16]}...>"
