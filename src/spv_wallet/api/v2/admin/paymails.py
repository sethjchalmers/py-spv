"""V2 admin paymail management — cross-user paymail operations."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_admin
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v2.schemas import PaginationParamsV2, PaymailResponseV2
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-admin-paymails"])


@router.get("/admin/paymails")
async def list_all_paymails(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    pagination: Annotated[PaginationParamsV2, Depends()],
) -> list[PaymailResponseV2]:
    """List all paymails across all users (admin only)."""
    paymails = await engine.v2.paymails.list_all(
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return [PaymailResponseV2.model_validate(p) for p in paymails]


@router.delete("/admin/paymails/{paymail_id}", status_code=204)
async def delete_paymail(
    paymail_id: int,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Delete a paymail by ID (admin only)."""
    await engine.v2.paymails.delete_paymail(paymail_id)
