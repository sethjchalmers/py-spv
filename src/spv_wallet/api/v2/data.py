"""V2 data (OP_RETURN) endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v2.schemas import DataResponse, PaginationParamsV2
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-data"])


@router.get("/data")
async def list_data(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    pagination: Annotated[PaginationParamsV2, Depends()],
) -> list[DataResponse]:
    """List OP_RETURN data outputs for the authenticated user."""
    from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository

    repo = TransactionRepository(engine.datastore)
    records = await repo.get_data_for_user(
        ctx.xpub_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return [
        DataResponse(
            tx_id=r.tx_id,
            vout=r.vout,
            user_id=r.user_id,
            blob_hex=r.blob.hex() if r.blob else "",
        )
        for r in records
    ]


@router.get("/data/{tx_id}")
async def get_data_for_tx(
    tx_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> list[DataResponse]:
    """Get OP_RETURN data outputs for a specific transaction."""
    from spv_wallet.engine.v2.database.repository.transactions import TransactionRepository

    repo = TransactionRepository(engine.datastore)
    records = await repo.get_data_for_tx(tx_id)
    return [
        DataResponse(
            tx_id=r.tx_id,
            vout=r.vout,
            user_id=r.user_id,
            blob_hex=r.blob.hex() if r.blob else "",
        )
        for r in records
    ]
