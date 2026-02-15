"""V1 paymail endpoints.

User-facing paymail address management.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import PaymailCreateRequest, PaymailResponse
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001
from spv_wallet.errors.definitions import ErrPaymailNotFound

router = APIRouter(tags=["paymail"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _paymail_resp(p: object) -> dict:
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
# Routes
# ---------------------------------------------------------------------------


@router.post("/paymail", status_code=201)
async def create_paymail(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: PaymailCreateRequest,
) -> dict:
    """Create a new paymail address for the current user."""
    pm = await engine.paymail_service.create_paymail(
        ctx.xpub_id,
        body.address,
        public_name=body.public_name,
        avatar=body.avatar,
        metadata=body.metadata,
    )
    return _paymail_resp(pm)


@router.get("/paymail")
async def list_paymails(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> list[dict]:
    """List paymail addresses for the current user."""
    paymails = await engine.paymail_service.get_paymails_by_xpub(ctx.xpub_id)
    return [_paymail_resp(p) for p in paymails]


@router.get("/paymail/{paymail_id}")
async def get_paymail(
    paymail_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a specific paymail address by ID."""
    pm = await engine.paymail_service.get_paymail_by_id(paymail_id)
    if pm is None or pm.xpub_id != ctx.xpub_id:
        raise ErrPaymailNotFound
    return _paymail_resp(pm)


@router.delete("/paymail/{address}", status_code=204)
async def delete_paymail(
    address: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Delete a paymail address."""
    # Verify ownership: parse alias@domain and check
    if "@" in address:
        alias, domain = address.split("@", 1)
        pm = await engine.paymail_service.get_paymail_by_alias(alias, domain)
    else:
        pm = await engine.paymail_service.get_paymail_by_id(address)

    if pm is None or pm.xpub_id != ctx.xpub_id:
        raise ErrPaymailNotFound

    await engine.paymail_service.delete_paymail(pm.alias + "@" + pm.domain)
