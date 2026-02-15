"""V2 transaction endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v2.schemas import (
    CreateOutlineRequest,
    OutlineInputResponse,
    OutlineOutputResponse,
    PaginationParamsV2,
    RecordTransactionRequest,
    TransactionOutlineResponse,
    TransactionResponseV2,
)
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001
from spv_wallet.engine.v2.transaction.outlines.models import OutlineOutput

router = APIRouter(tags=["v2-transactions"])


@router.post("/transactions/outlines")
async def create_outline(
    body: CreateOutlineRequest,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> TransactionOutlineResponse:
    """Create a transaction outline (unsigned template) for the user."""
    outputs = [
        OutlineOutput(
            to=o.to,
            satoshis=o.satoshis,
            op_return=bytes.fromhex(o.op_return) if o.op_return else None,
        )
        for o in body.outputs
    ]
    outline = await engine.v2.outlines.create(ctx.xpub_id, outputs)
    return TransactionOutlineResponse(
        user_id=outline.user_id,
        inputs=[
            OutlineInputResponse(
                tx_id=i.tx_id,
                vout=i.vout,
                satoshis=i.satoshis,
                estimated_size=i.estimated_size,
            )
            for i in outline.inputs
        ],
        outputs=[
            OutlineOutputResponse(
                to=o.to,
                satoshis=o.satoshis,
                op_return=o.op_return.hex() if o.op_return else None,
            )
            for o in outline.outputs
        ],
        fee=outline.fee,
        total_input=outline.total_input,
        total_output=outline.total_output,
        change=outline.change,
    )


@router.post("/transactions/record", status_code=201)
async def record_transaction(
    body: RecordTransactionRequest,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> TransactionResponseV2:
    """Record a signed transaction."""
    result = await engine.v2.record.record_transaction_outline(
        ctx.xpub_id,
        body.raw_hex,
        beef_hex=body.beef_hex,
    )
    return TransactionResponseV2.model_validate(result.tracked_tx)


@router.get("/transactions/{tx_id}")
async def get_transaction(
    tx_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> TransactionResponseV2:
    """Get a tracked transaction by ID."""
    from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository
    from spv_wallet.errors.definitions import ErrTransactionNotFound

    repo = TransactionRepository(engine.datastore)
    tx = await repo.get_transaction(tx_id)
    if tx is None:
        raise ErrTransactionNotFound
    return TransactionResponseV2.model_validate(tx)


@router.get("/transactions")
async def list_transactions(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    pagination: Annotated[PaginationParamsV2, Depends()],
) -> list[TransactionResponseV2]:
    """List tracked transactions."""
    from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository

    repo = TransactionRepository(engine.datastore)
    txs = await repo.list_transactions(page=pagination.page, page_size=pagination.page_size)
    return [TransactionResponseV2.model_validate(tx) for tx in txs]
