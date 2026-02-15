"""V2 admin user management.

Re-exports the user router from api/v2/users since all user CRUD is
already admin-only.  This module adds any admin-specific user operations
that go beyond basic CRUD (e.g., paymail assignment for a user).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_admin
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v2.schemas import (
    PaginationParamsV2,
    PaymailCreateRequestV2,
    PaymailResponseV2,
)
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-admin-users"])


@router.post("/admin/users/{user_id}/paymails", status_code=201)
async def create_paymail_for_user(
    user_id: str,
    body: PaymailCreateRequestV2,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> PaymailResponseV2:
    """Create a paymail for a specific user (admin only)."""
    paymail = await engine.v2.paymails.create_paymail(
        user_id,
        alias=body.alias,
        domain=body.domain,
        public_name=body.public_name,
        avatar=body.avatar,
    )
    return PaymailResponseV2.model_validate(paymail)


@router.get("/admin/users/{user_id}/paymails")
async def list_paymails_for_user(
    user_id: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    pagination: Annotated[PaginationParamsV2, Depends()],
) -> list[PaymailResponseV2]:
    """List paymails for a specific user (admin only)."""
    paymails = await engine.v2.paymails.list_for_user(
        user_id,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return [PaymailResponseV2.model_validate(p) for p in paymails]
