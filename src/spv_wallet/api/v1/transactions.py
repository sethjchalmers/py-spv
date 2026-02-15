"""V1 transaction endpoints.

User-facing transaction operations: draft, record, list, get, callback.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import (
    ArcCallbackRequest,
    DraftTransactionRequest,
    DraftTransactionResponse,
    RecordTransactionRequest,
    TransactionResponse,
)
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001
from spv_wallet.errors.definitions import ErrTransactionNotFound

router = APIRouter(tags=["transaction"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tx_resp(t: object) -> dict:
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


def _draft_resp(d: object) -> dict:
    return DraftTransactionResponse(
        id=d.id,
        xpub_id=d.xpub_id,
        config=d.config,
        status=d.status,
        final_tx_id=d.final_tx_id,
        hex_body=d.hex_body,
        reference_id=d.reference_id,
        total_value=d.total_value,
        fee=d.fee,
        metadata=d.metadata_,
        created_at=d.created_at,
        updated_at=d.updated_at,
    ).model_dump(mode="json")


def _output_to_dict(o: Any) -> dict[str, Any]:
    """Convert a TransactionOutput schema to a service-level dict."""
    d: dict[str, Any] = {}
    if o.to:
        d["to"] = o.to
        d["satoshis"] = o.satoshis
    if o.op_return:
        d["op_return"] = o.op_return
    if o.script:
        d["script"] = o.script
        d["satoshis"] = o.satoshis
    return d


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/transaction", status_code=201)
async def create_draft_transaction(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: DraftTransactionRequest,
) -> dict:
    """Create a new draft transaction."""
    outputs = [_output_to_dict(o) for o in body.outputs]
    draft = await engine.transaction_service.new_transaction(
        ctx.xpub_id,
        outputs=outputs,
        metadata=body.metadata,
    )
    return _draft_resp(draft)


@router.post("/transaction/record", status_code=201)
async def record_transaction(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: RecordTransactionRequest,
) -> dict:
    """Record a signed transaction."""
    tx = await engine.transaction_service.record_transaction(
        ctx.xpub_id,
        body.hex,
        draft_id=body.draft_id,
        metadata=body.metadata,
    )
    return _tx_resp(tx)


@router.get("/transaction")
async def list_transactions(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    status: str | None = None,
) -> list[dict]:
    """List transactions for the current user."""
    txs = await engine.transaction_service.get_transactions(
        ctx.xpub_id,
        status=status,
    )
    return [_tx_resp(t) for t in txs]


@router.get("/transaction/{txid}")
async def get_transaction(
    txid: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a specific transaction by txid."""
    tx = await engine.transaction_service.get_transaction(txid)
    if tx is None or tx.xpub_id != ctx.xpub_id:
        raise ErrTransactionNotFound
    return _tx_resp(tx)


@router.get("/transaction/draft/{draft_id}")
async def get_draft(
    draft_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a draft transaction by ID."""
    from spv_wallet.errors.definitions import ErrDraftNotFound

    draft = await engine.transaction_service.get_draft(draft_id)
    if draft is None or draft.xpub_id != ctx.xpub_id:
        raise ErrDraftNotFound
    return _draft_resp(draft)


@router.post("/transaction/broadcast/callback")
async def arc_callback(
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: ArcCallbackRequest,
) -> dict:
    """Handle an ARC broadcast callback (no auth required)."""
    await engine.transaction_service.handle_arc_callback(
        body.txid,
        body.tx_status,
        block_hash=body.block_hash,
        block_height=body.block_height,
        merkle_path=body.merkle_path,
        competing_txs=body.competing_txs or None,
    )
    return {"status": "ok"}
