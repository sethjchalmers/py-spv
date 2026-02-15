"""V2 SQLAlchemy ORM models.

Mirrors the Go ``engine/v2/database/models.go`` set.  V2 uses a cleaner
user-centric design: users are identified by public key (not xPub), transactions
are tracked as outlines, and outputs/UTXOs are managed separately.
"""

from __future__ import annotations

import enum
from datetime import datetime  # noqa: TC003 - SQLAlchemy needs this at runtime for Mapped[datetime]

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from spv_wallet.engine.models.base import Base

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TxStatusV2(enum.StrEnum):
    """V2 transaction status values."""

    CREATED = "CREATED"
    BROADCASTED = "BROADCASTED"
    SEEN_ON_NETWORK = "SEEN_ON_NETWORK"
    MINED = "MINED"
    REJECTED = "REJECTED"
    PROBLEMATIC = "PROBLEMATIC"


class OperationType(enum.StrEnum):
    """Type of user operation on a transaction."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"
    DATA = "data"


class ContactStatus(enum.StrEnum):
    """Status of a user contact relationship."""

    UNCONFIRMED = "unconfirmed"
    AWAITING = "awaiting"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class UserV2(Base):
    """User identified by public key.

    V2 users are simpler than V1 xPubs — they're keyed by a 34-char
    compressed public key, not a 64-char SHA-256 hash of an xPub.
    """

    __tablename__ = "v2_users"

    id: Mapped[str] = mapped_column(
        String(34),
        primary_key=True,
        comment="Compressed public key",
    )
    pub_key: Mapped[str] = mapped_column(
        String(66),
        unique=True,
        nullable=False,
        index=True,
        comment="Hex-encoded compressed public key",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    paymails: Mapped[list[PaymailV2]] = relationship(
        "PaymailV2",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    addresses: Mapped[list[AddressV2]] = relationship(
        "AddressV2",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    contacts: Mapped[list[UserContact]] = relationship(
        "UserContact",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<UserV2 id={self.id}>"


class PaymailV2(Base):
    """Paymail address attached to a V2 user."""

    __tablename__ = "v2_paymails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    public_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    avatar: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    user_id: Mapped[str] = mapped_column(
        String(34),
        ForeignKey("v2_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    # Relationships
    user: Mapped[UserV2] = relationship("UserV2", back_populates="paymails")

    __table_args__ = (
        # Unique together (alias, domain) when not deleted
        {"comment": "V2 paymail addresses"},
    )

    def __repr__(self) -> str:
        return f"<PaymailV2 {self.alias}@{self.domain}>"


class AddressV2(Base):
    """Bitcoin address with optional custom unlock instructions."""

    __tablename__ = "v2_addresses"

    address: Mapped[str] = mapped_column(
        String(34),
        primary_key=True,
        comment="Base58Check P2PKH address",
    )
    custom_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-encoded custom unlock instructions",
    )
    user_id: Mapped[str] = mapped_column(
        String(34),
        ForeignKey("v2_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    # Relationships
    user: Mapped[UserV2] = relationship("UserV2", back_populates="addresses")

    def __repr__(self) -> str:
        return f"<AddressV2 {self.address}>"


class TrackedTransaction(Base):
    """Tracked transaction with BEEF/raw hex and block info.

    The central V2 transaction record — stores broadcast status, Merkle
    proof data, and references to inputs/outputs.
    """

    __tablename__ = "v2_tracked_transactions"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="Transaction ID (txid)",
    )
    tx_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=TxStatusV2.CREATED.value,
        comment="Transaction lifecycle status",
    )
    block_height: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    block_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    beef_hex: Mapped[str | None] = mapped_column(Text, nullable=True, comment="BEEF-encoded hex")
    raw_hex: Mapped[str | None] = mapped_column(Text, nullable=True, comment="Raw transaction hex")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    source_tx_inputs: Mapped[list[TxInput]] = relationship(
        "TxInput",
        back_populates="transaction",
        cascade="all, delete-orphan",
        foreign_keys="TxInput.tx_id",
    )
    outputs: Mapped[list[TrackedOutput]] = relationship(
        "TrackedOutput",
        back_populates="transaction",
        foreign_keys="TrackedOutput.tx_id",
    )
    data: Mapped[list[DataV2]] = relationship(
        "DataV2",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<TrackedTransaction {self.id[:16]}... status={self.tx_status}>"


class TrackedOutput(Base):
    """Transaction output tracking ownership and spend status.

    Links outputs to their creating transaction and (optionally) their
    spending transaction.
    """

    __tablename__ = "v2_tracked_outputs"

    tx_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("v2_tracked_transactions.id"),
        primary_key=True,
    )
    vout: Mapped[int] = mapped_column(Integer, primary_key=True)
    spending_tx: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="Txid that spent this output",
    )
    user_id: Mapped[str] = mapped_column(String(34), nullable=False, index=True)
    satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    transaction: Mapped[TrackedTransaction] = relationship(
        "TrackedTransaction",
        back_populates="outputs",
        foreign_keys=[tx_id],
    )

    @property
    def is_spent(self) -> bool:
        """Check if this output has been spent."""
        return bool(self.spending_tx.strip())

    def __repr__(self) -> str:
        return f"<TrackedOutput {self.tx_id[:16]}:{self.vout} sats={self.satoshis}>"


class TxInput(Base):
    """Source transaction input reference for BEEF ancestry.

    Links a spending transaction to its source transaction(s),
    enabling ancestry traversal for BEEF construction.
    """

    __tablename__ = "v2_tx_inputs"

    tx_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("v2_tracked_transactions.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Spending transaction ID",
    )
    source_tx_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="Source transaction ID",
    )

    # Relationships
    transaction: Mapped[TrackedTransaction] = relationship(
        "TrackedTransaction",
        back_populates="source_tx_inputs",
        foreign_keys=[tx_id],
    )

    def __repr__(self) -> str:
        return f"<TxInput spending={self.tx_id[:16]} source={self.source_tx_id[:16]}>"


class UserUTXO(Base):
    """User's unspent transaction output.

    Separate from TrackedOutput — this is the user-facing UTXO set
    with additional metadata for coin selection (bucket, estimated size,
    custom instructions).
    """

    __tablename__ = "v2_user_utxos"

    user_id: Mapped[str] = mapped_column(String(34), primary_key=True)
    tx_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vout: Mapped[int] = mapped_column(Integer, primary_key=True)
    satoshis: Mapped[int] = mapped_column(BigInteger, nullable=False)
    estimated_input_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=148,
        comment="Estimated size in bytes when spent",
    )
    bucket: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="bsv",
        comment="UTXO bucket (bsv, token, etc.) — never 'data'",
    )
    custom_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-encoded custom unlock instructions",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    touched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Last time this UTXO was considered for selection",
    )

    def __repr__(self) -> str:
        return f"<UserUTXO {self.user_id[:8]}:{self.tx_id[:16]}:{self.vout} sats={self.satoshis}>"


class Operation(Base):
    """User-level operation on a transaction.

    Records how each transaction affects each user — incoming payment,
    outgoing spend, or data-only operation.
    """

    __tablename__ = "v2_operations"

    tx_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(34),
        ForeignKey("v2_users.id"),
        primary_key=True,
    )
    type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="incoming, outgoing, or data",
    )
    value: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Net value change in satoshis",
    )
    counterparty: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
        comment="Counterparty paymail or pubkey",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[UserV2] = relationship("UserV2")

    def __repr__(self) -> str:
        return (
            f"<Operation {self.type} tx={self.tx_id[:16]} user={self.user_id[:8]} val={self.value}>"
        )


class DataV2(Base):
    """OP_RETURN data output stored per transaction.

    Captures the raw OP_RETURN payload from data-bearing outputs.
    """

    __tablename__ = "v2_data"

    tx_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("v2_tracked_transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    vout: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(34), nullable=False, index=True)
    blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, default=b"")

    # Relationships
    transaction: Mapped[TrackedTransaction] = relationship(
        "TrackedTransaction",
        back_populates="data",
    )

    def __repr__(self) -> str:
        return f"<DataV2 tx={self.tx_id[:16]}:{self.vout} size={len(self.blob)}>"


class UserContact(Base):
    """Contact relationship between V2 users."""

    __tablename__ = "v2_user_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ContactStatus.UNCONFIRMED.value,
    )
    paymail: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    pub_key: Mapped[str] = mapped_column(String(66), nullable=False, default="")
    user_id: Mapped[str] = mapped_column(
        String(34),
        ForeignKey("v2_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
    )

    # Relationships
    user: Mapped[UserV2] = relationship("UserV2", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<UserContact {self.full_name} status={self.status}>"


# ---------------------------------------------------------------------------
# All V2 models for migration registration
# ---------------------------------------------------------------------------

ALL_V2_MODELS: list[type[Base]] = [
    UserV2,
    PaymailV2,
    AddressV2,
    TrackedTransaction,
    TrackedOutput,
    TxInput,
    UserUTXO,
    Operation,
    DataV2,
    UserContact,
]

__all__ = [
    "ALL_V2_MODELS",
    "AddressV2",
    "ContactStatus",
    "DataV2",
    "Operation",
    "OperationType",
    "PaymailV2",
    "TrackedOutput",
    "TrackedTransaction",
    "TxInput",
    "TxStatusV2",
    "UserContact",
    "UserUTXO",
    "UserV2",
]
