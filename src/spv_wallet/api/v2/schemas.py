"""V2 API request/response schemas (Pydantic models)."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - Pydantic needs this at runtime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


class PaginationParamsV2(BaseModel):
    """Common pagination query parameters for V2 endpoints."""

    page: int = Field(1, ge=1, description="Page number (1-based)")
    page_size: int = Field(50, ge=1, le=200, alias="pageSize", description="Items per page")

    model_config = {"populate_by_name": True}


class ErrorResponseV2(BaseModel):
    """Standard error response."""

    code: str
    message: str


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class UserCreateRequest(BaseModel):
    """Create a V2 user."""

    pub_key: str = Field(..., alias="pubKey", description="Hex-encoded compressed public key")

    model_config = {"populate_by_name": True}


class UserResponse(BaseModel):
    """V2 user response."""

    id: str
    pub_key: str = Field(alias="pubKey")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


# ---------------------------------------------------------------------------
# Paymails
# ---------------------------------------------------------------------------


class PaymailCreateRequestV2(BaseModel):
    """Create a V2 paymail."""

    alias: str
    domain: str
    public_name: str = Field("", alias="publicName")
    avatar: str = ""

    model_config = {"populate_by_name": True}


class PaymailResponseV2(BaseModel):
    """V2 paymail response."""

    id: int
    alias: str
    domain: str
    public_name: str = Field(alias="publicName")
    avatar: str
    user_id: str = Field(alias="userId")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------


class ContactCreateRequestV2(BaseModel):
    """Create a V2 contact."""

    full_name: str = Field(..., alias="fullName")
    paymail: str = ""
    pub_key: str = Field("", alias="pubKey")

    model_config = {"populate_by_name": True}


class ContactStatusUpdateV2(BaseModel):
    """Update a V2 contact status."""

    status: str


class ContactResponseV2(BaseModel):
    """V2 contact response."""

    id: int
    full_name: str = Field(alias="fullName")
    status: str
    paymail: str
    pub_key: str = Field(alias="pubKey")
    user_id: str = Field(alias="userId")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class OutlineOutputRequest(BaseModel):
    """A single output in a transaction outline request."""

    to: str
    satoshis: int = Field(..., ge=1)
    op_return: str | None = Field(None, alias="opReturn", description="Hex-encoded OP_RETURN data")

    model_config = {"populate_by_name": True}


class CreateOutlineRequest(BaseModel):
    """Request to create a transaction outline."""

    outputs: list[OutlineOutputRequest]

    model_config = {"populate_by_name": True}


class OutlineInputResponse(BaseModel):
    """A selected input in the outline response."""

    tx_id: str = Field(alias="txId")
    vout: int
    satoshis: int
    estimated_size: int = Field(alias="estimatedSize")

    model_config = {"populate_by_name": True}


class OutlineOutputResponse(BaseModel):
    """An output in the outline response."""

    to: str
    satoshis: int
    op_return: str | None = Field(None, alias="opReturn")

    model_config = {"populate_by_name": True}


class TransactionOutlineResponse(BaseModel):
    """Response with the created transaction outline."""

    user_id: str = Field(alias="userId")
    inputs: list[OutlineInputResponse]
    outputs: list[OutlineOutputResponse]
    fee: int
    total_input: int = Field(alias="totalInput")
    total_output: int = Field(alias="totalOutput")
    change: int

    model_config = {"populate_by_name": True}


class RecordTransactionRequest(BaseModel):
    """Request to record a signed transaction."""

    raw_hex: str = Field(..., alias="rawHex")
    beef_hex: str | None = Field(None, alias="beefHex")

    model_config = {"populate_by_name": True}


class TransactionResponseV2(BaseModel):
    """V2 transaction response."""

    id: str
    tx_status: str = Field(alias="txStatus")
    block_height: int | None = Field(None, alias="blockHeight")
    block_hash: str | None = Field(None, alias="blockHash")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


class OperationResponse(BaseModel):
    """V2 operation response."""

    tx_id: str = Field(alias="txId")
    user_id: str = Field(alias="userId")
    type: str
    value: int
    counterparty: str
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True, "from_attributes": True}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


class DataResponse(BaseModel):
    """V2 data output response."""

    tx_id: str = Field(alias="txId")
    vout: int
    user_id: str = Field(alias="userId")
    blob_hex: str = Field(alias="blobHex")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# ARC Callback
# ---------------------------------------------------------------------------


class ArcCallbackRequestV2(BaseModel):
    """ARC broadcast callback for V2."""

    txid: str
    tx_status: str = Field(alias="txStatus")
    block_height: int | None = Field(None, alias="blockHeight")
    block_hash: str | None = Field(None, alias="blockHash")
    merkle_path: str | None = Field(None, alias="merklePath")

    model_config = {"populate_by_name": True}
