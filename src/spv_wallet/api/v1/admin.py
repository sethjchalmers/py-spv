"""V1 admin endpoints.

Admin-only CRUD operations for xPubs, paymails, contacts, transactions,
UTXOs, and access keys.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_admin
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import (
    MetadataUpdateRequest,
    PaymailCreateRequest,
    PaymailResponse,
    TransactionResponse,
    UTXOResponse,
    XPubCreateRequest,
    XPubResponse,
)
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Helpers — reuse response schema constructors
# ---------------------------------------------------------------------------


def _xpub_resp(x: Any) -> dict:
    return XPubResponse(
        id=x.id,
        current_balance=x.current_balance,
        next_internal_num=x.next_internal_num,
        next_external_num=x.next_external_num,
        metadata=x.metadata_,
        created_at=x.created_at,
        updated_at=x.updated_at,
    ).model_dump(mode="json")


def _tx_resp(t: Any) -> dict:
    return TransactionResponse(
        id=t.id,
        xpub_id=t.xpub_id,
        hex_body=t.hex_body,
        block_hash=t.block_hash,
        block_height=t.block_height,
        merkle_path=t.merkle_path,
        total_value=t.total_value,
        fee=t.fee,
        status=t.status,
        direction=t.direction,
        num_inputs=t.num_inputs,
        num_outputs=t.num_outputs,
        draft_id=t.draft_id,
        metadata=t.metadata_,
        created_at=t.created_at,
        updated_at=t.updated_at,
    ).model_dump(mode="json")


def _utxo_resp(u: Any) -> dict:
    return UTXOResponse(
        id=u.id,
        xpub_id=u.xpub_id,
        transaction_id=u.transaction_id,
        output_index=u.output_index,
        satoshis=u.satoshis,
        script_pub_key=u.script_pub_key,
        type=u.type,
        destination_id=u.destination_id,
        spending_tx_id=u.spending_tx_id,
        draft_id=u.draft_id,
        metadata=u.metadata_,
        created_at=u.created_at,
        updated_at=u.updated_at,
    ).model_dump(mode="json")


def _paymail_resp(p: Any) -> dict:
    return PaymailResponse(
        id=p.id,
        xpub_id=p.xpub_id,
        alias=p.alias,
        domain=p.domain,
        public_name=p.public_name,
        avatar=p.avatar,
        metadata=p.metadata_,
        created_at=p.created_at,
        updated_at=p.updated_at,
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# XPub admin routes
# ---------------------------------------------------------------------------


@router.post("/xpub", status_code=201)
async def register_xpub(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: XPubCreateRequest,
) -> dict:
    """Register a new xPub (admin only)."""
    xpub = await engine.xpub_service.new_xpub(body.xpub, metadata=body.metadata)
    return _xpub_resp(xpub)


@router.get("/xpub/{xpub_id}")
async def get_xpub(
    xpub_id: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get an xPub by ID (admin only)."""
    xpub = await engine.xpub_service.get_xpub_by_id(xpub_id, required=True)
    return _xpub_resp(xpub)


@router.patch("/xpub/{xpub_id}/metadata")
async def update_xpub_metadata(
    xpub_id: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: MetadataUpdateRequest,
) -> dict:
    """Update xPub metadata (admin only)."""
    xpub = await engine.xpub_service.update_metadata(xpub_id, body.metadata)
    return _xpub_resp(xpub)


@router.delete("/xpub/{xpub_id}", status_code=204)
async def delete_xpub(
    xpub_id: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Soft-delete an xPub (admin only)."""
    await engine.xpub_service.delete_xpub(xpub_id)


# ---------------------------------------------------------------------------
# Transaction admin routes
# ---------------------------------------------------------------------------


@router.get("/transaction")
async def list_transactions(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    xpub_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """List transactions (admin only, optionally filtered by xpub_id)."""
    if xpub_id:
        txs = await engine.transaction_service.get_transactions(xpub_id, status=status)
    else:
        # List across all users — use empty xpub_id to get all
        txs = await engine.transaction_service.get_transactions("", status=status)
    return [_tx_resp(t) for t in txs]


@router.get("/transaction/{txid}")
async def get_transaction(
    txid: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a transaction by txid (admin only)."""
    from spv_wallet.errors.definitions import ErrTransactionNotFound

    tx = await engine.transaction_service.get_transaction(txid)
    if tx is None:
        raise ErrTransactionNotFound
    return _tx_resp(tx)


# ---------------------------------------------------------------------------
# UTXO admin routes
# ---------------------------------------------------------------------------


@router.get("/utxo")
async def list_utxos(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    xpub_id: str | None = None,
    unspent_only: bool = False,
) -> list[dict]:
    """List UTXOs (admin only)."""
    utxos = await engine.utxo_service.get_utxos(xpub_id=xpub_id, unspent_only=unspent_only)
    return [_utxo_resp(u) for u in utxos]


# ---------------------------------------------------------------------------
# Paymail admin routes
# ---------------------------------------------------------------------------


@router.post("/paymail", status_code=201)
async def create_paymail(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: PaymailCreateRequest,
    xpub_id: str = "",
) -> dict:
    """Create a paymail for any user (admin only).

    The ``xpub_id`` query parameter specifies which user gets the paymail.
    """
    target_xpub_id = xpub_id or ctx.xpub_id
    pm = await engine.paymail_service.create_paymail(
        target_xpub_id,
        body.address,
        public_name=body.public_name,
        avatar=body.avatar,
        metadata=body.metadata,
    )
    return _paymail_resp(pm)


@router.get("/paymail")
async def list_paymails(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    xpub_id: str | None = None,
) -> list[dict]:
    """List paymails (admin only, optionally filtered by xpub_id)."""
    paymails = await engine.paymail_service.search_paymails(xpub_id=xpub_id)
    return [_paymail_resp(p) for p in paymails]


@router.delete("/paymail/{address}", status_code=204)
async def delete_paymail(
    address: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Delete a paymail address (admin only)."""
    await engine.paymail_service.delete_paymail(address)


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------


@router.get("/health")
async def admin_health(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Detailed health check (admin only)."""
    return await engine.health_check()
