"""Transaction model — recorded transactions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, ModelOps, TimestampMixin


class Transaction(Base, TimestampMixin, MetadataMixin, ModelOps):
    """A recorded transaction with hex, BEEF, block info, and status.

    Stores the full transaction lifecycle data including broadcast
    status, block confirmation, and Merkle proof.
    """

    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="Transaction ID (txid hex)"
    )
    xpub_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Owning xPub ID"
    )
    hex_body: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="Raw transaction hex"
    )
    beef_hex: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="BEEF-encoded transaction hex"
    )
    block_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="Block hash (if mined)"
    )
    block_height: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="Block height (if mined)"
    )
    merkle_path: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="Merkle path proof (JSON or BRC-71)"
    )
    fee: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="Transaction fee in satoshis"
    )
    total_value: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="Total satoshis transferred"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="created",
        comment="created | broadcast | seen_on_network | mined | rejected",
    )
    direction: Mapped[str] = mapped_column(
        String(16), nullable=False, default="outgoing",
        comment="incoming | outgoing",
    )
    number_of_inputs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Number of inputs"
    )
    number_of_outputs: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="Number of outputs"
    )
    draft_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", comment="Associated draft transaction ID"
    )

    def __repr__(self) -> str:
        return f"<Transaction id={self.id[:16]}... status={self.status}>"
