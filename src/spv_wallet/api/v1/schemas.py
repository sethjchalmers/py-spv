"""V1 API request/response Pydantic schemas.

These are the *API-layer* schemas — thin wrappers that define the HTTP
contract.  They deliberately do NOT inherit from SQLAlchemy models; the
endpoint code maps between ORM objects and these schemas.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic needs this at runtime for Mapped[datetime]
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Generic / Pagination
# ---------------------------------------------------------------------------


class PaginationParams(BaseModel):
    """Common pagination query parameters."""

    limit: int = Field(50, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class PaginatedResponse(BaseModel):
    """Generic paginated list wrapper."""

    items: list[Any]
    total: int
    limit: int
    offset: int


class MetadataFilter(BaseModel):
    """Optional metadata filter for list endpoints."""

    metadata: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error body — matches Go ``{"code": "...", "message": "..."}``."""

    code: str
    message: str


# ---------------------------------------------------------------------------
# XPub
# ---------------------------------------------------------------------------


class XPubCreateRequest(BaseModel):
    """POST /api/v1/admin/xpubs — register a new xPub."""

    xpub: str
    metadata: dict[str, Any] | None = None


class XPubResponse(BaseModel):
    """Serialised xPub for API responses."""

    id: str
    current_balance: int = 0
    next_internal_num: int = 0
    next_external_num: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Destination
# ---------------------------------------------------------------------------


class DestinationCreateRequest(BaseModel):
    """POST /api/v1/destination — create a new destination."""

    metadata: dict[str, Any] | None = None


class DestinationResponse(BaseModel):
    """Serialised destination for API responses."""

    id: str
    xpub_id: str
    locking_script: str
    type: str
    chain: int
    num: int
    address: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Access Key
# ---------------------------------------------------------------------------


class AccessKeyCreateResponse(BaseModel):
    """Response for creating a new access key (includes private key)."""

    id: str
    xpub_id: str
    key: str  # public key hex
    private_key: str  # returned once on creation
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class AccessKeyResponse(BaseModel):
    """Serialised access key for API responses."""

    id: str
    xpub_id: str
    key: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    deleted_at: datetime | None = None


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class TransactionOutput(BaseModel):
    """A single output in a transaction draft request."""

    to: str | None = None  # paymail or address
    satoshis: int = 0
    op_return: str | None = None  # hex-encoded OP_RETURN data
    script: str | None = None  # raw output script


class DraftTransactionRequest(BaseModel):
    """POST /api/v1/transaction — create a draft transaction."""

    outputs: list[TransactionOutput]
    metadata: dict[str, Any] | None = None


class RecordTransactionRequest(BaseModel):
    """POST /api/v1/transaction/record — record a signed transaction."""

    hex: str
    draft_id: str = ""
    metadata: dict[str, Any] | None = None


class DraftTransactionResponse(BaseModel):
    """Serialised draft transaction."""

    id: str
    xpub_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str
    final_tx_id: str | None = None
    hex_body: str = ""
    reference_id: str = ""
    total_value: int = 0
    fee: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TransactionResponse(BaseModel):
    """Serialised transaction."""

    id: str
    xpub_id: str
    hex_body: str = ""
    block_hash: str = ""
    block_height: int = 0
    merkle_path: str = ""
    total_value: int = 0
    fee: int = 0
    status: str = "created"
    direction: str = "outgoing"
    num_inputs: int = 0
    num_outputs: int = 0
    draft_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# UTXO
# ---------------------------------------------------------------------------


class UTXOResponse(BaseModel):
    """Serialised UTXO."""

    id: str
    xpub_id: str
    transaction_id: str
    output_index: int
    satoshis: int
    script_pub_key: str
    type: str = "pubkeyhash"
    destination_id: str = ""
    spending_tx_id: str = ""
    draft_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Contact
# ---------------------------------------------------------------------------


class ContactCreateRequest(BaseModel):
    """POST /api/v1/contact — create a new contact."""

    paymail: str
    full_name: str = ""
    metadata: dict[str, Any] | None = None


class ContactUpdateStatusRequest(BaseModel):
    """PATCH /api/v1/contact/{id}/status — update contact status."""

    status: str


class ContactResponse(BaseModel):
    """Serialised contact."""

    id: str
    xpub_id: str
    full_name: str = ""
    paymail: str
    pub_key: str = ""
    status: str = "unconfirmed"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Paymail
# ---------------------------------------------------------------------------


class PaymailCreateRequest(BaseModel):
    """POST /api/v1/paymail — create a paymail address."""

    address: str  # e.g. "user@example.com"
    public_name: str = ""
    avatar: str = ""
    metadata: dict[str, Any] | None = None


class PaymailResponse(BaseModel):
    """Serialised paymail address."""

    id: str
    xpub_id: str
    alias: str
    domain: str
    public_name: str = ""
    avatar: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Shared Config
# ---------------------------------------------------------------------------


class SharedConfigResponse(BaseModel):
    """Public configuration exposed to clients."""

    paymail_domains: list[str]
    experimental_features: dict[str, bool] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# ARC Callback
# ---------------------------------------------------------------------------


class ArcCallbackRequest(BaseModel):
    """POST /api/v1/transaction/broadcast/callback — ARC miner callback."""

    txid: str = Field(alias="txID")
    tx_status: str = Field(alias="txStatus")
    block_hash: str = Field("", alias="blockHash")
    block_height: int = Field(0, alias="blockHeight")
    merkle_path: str = Field("", alias="merklePath")
    competing_txs: list[str] = Field(default_factory=list, alias="competingTxs")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Metadata Update
# ---------------------------------------------------------------------------


class MetadataUpdateRequest(BaseModel):
    """PATCH metadata on any model."""

    metadata: dict[str, Any]
