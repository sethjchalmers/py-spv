"""DraftTransaction model — unsigned transaction templates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, ModelOps, TimestampMixin


class DraftTransaction(Base, TimestampMixin, MetadataMixin, ModelOps):
    """An unsigned transaction template with full configuration.

    Stores the draft's inputs, outputs, fee computation, and change
    destinations. The draft is finalized when the client signs it
    and submits the resulting hex.
    """

    __tablename__ = "draft_transactions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="Unique draft ID (UUID or hash)"
    )
    xpub_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Owning xPub ID"
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="TransactionConfig JSON"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft",
        comment="draft | canceled | complete | expired",
    )
    expires_at: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="ISO-8601 expiration timestamp"
    )
    hex_body: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="Unsigned transaction hex"
    )
    final_tx_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="Final txid after signing"
    )
    total_value: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="Total satoshis in draft"
    )
    fee: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="Computed fee in satoshis"
    )

    def __repr__(self) -> str:
        return f"<DraftTransaction id={self.id[:16]}... status={self.status}>"
