"""V2 operation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v2.schemas import OperationResponse, PaginationParamsV2
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-operations"])


@router.get("/operations")
async def list_operations(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    pagination: Annotated[PaginationParamsV2, Depends()],
    op_type: str | None = None,
) -> list[OperationResponse]:
    """List operations for the authenticated user."""
    from spv_wallet.engine.v2.database.repository.operations import OperationRepository

    repo = OperationRepository(engine.datastore)
    ops = await repo.list_by_user(
        ctx.xpub_id,
        op_type=op_type,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return [OperationResponse.model_validate(op) for op in ops]


@router.get("/operations/{tx_id}")
async def get_operation(
    tx_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> OperationResponse:
    """Get an operation by transaction ID for the authenticated user."""
    from spv_wallet.engine.v2.database.repository.operations import OperationRepository
    from spv_wallet.errors.definitions import ErrOperationNotFound

    repo = OperationRepository(engine.datastore)
    op = await repo.get(tx_id, ctx.xpub_id)
    if op is None:
        raise ErrOperationNotFound
    return OperationResponse.model_validate(op)
