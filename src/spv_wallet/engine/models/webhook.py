"""Webhook model — webhook subscriptions."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, ModelOps, TimestampMixin


class Webhook(Base, TimestampMixin, MetadataMixin, ModelOps):
    """A registered webhook subscription for event notifications.

    Webhooks are called when specific events occur (e.g., transaction
    confirmed, UTXO received).
    """

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="Unique webhook ID")
    url: Mapped[str] = mapped_column(Text, nullable=False, comment="Callback URL")
    token_header: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Authorization",
        comment="HTTP header name for token",
    )
    token_value: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="Bearer token value"
    )
    banned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the webhook has been banned due to failures",
    )

    def __repr__(self) -> str:
        return f"<Webhook id={self.id[:16]}... url={self.url[:30]}>"
