"""Destination model — derived BIP32 addresses."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from spv_wallet.engine.models.base import Base, MetadataMixin, TimestampMixin


class Destination(Base, TimestampMixin, MetadataMixin):
    """A derived P2PKH address (BIP32 chain + index) with its locking script.

    Each destination is associated with an xPub and tracks the BIP32
    derivation path used to generate the address.
    """

    __tablename__ = "destinations"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="SHA-256 hash of locking script"
    )
    xpub_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Owning xPub ID"
    )
    locking_script: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Hex-encoded locking script"
    )
    type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pubkeyhash", comment="Script type"
    )
    chain: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="BIP32 chain (0=external, 1=internal)"
    )
    num: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="BIP32 index within chain"
    )
    address: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="Base58Check P2PKH address"
    )

    def __repr__(self) -> str:
        return f"<Destination address={self.address} chain={self.chain}/{self.num}>"
