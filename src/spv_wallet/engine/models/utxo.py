"""UTXO model — unspent transaction outputs."""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, ModelOps, TimestampMixin


class UTXO(Base, TimestampMixin, MetadataMixin, ModelOps):
    """An unspent transaction output tracked per user.

    Each UTXO is identified by its ``(transaction_id, output_index)`` pair
    and linked to an xPub via ``xpub_id``.
    """

    __tablename__ = "utxos"

    id: Mapped[str] = mapped_column(
        String(128), primary_key=True, comment="txid:vout composite key"
    )
    xpub_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Owning xPub ID"
    )
    transaction_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Transaction ID (txid)"
    )
    output_index: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Output index (vout)"
    )
    satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="Value in satoshis")
    script_pub_key: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Hex-encoded locking script"
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pubkeyhash", comment="Script type"
    )
    spending_tx_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="Transaction ID that spent this UTXO (empty if unspent)",
    )
    draft_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="Draft transaction ID that reserved this UTXO",
    )
    destination_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="Associated destination ID"
    )

    @property
    def is_spent(self) -> bool:
        """Check if this UTXO has been spent."""
        return bool(self.spending_tx_id)

    def __repr__(self) -> str:
        return f"<Utxo {self.transaction_id[:16]}:{self.output_index} sats={self.satoshis}>"
