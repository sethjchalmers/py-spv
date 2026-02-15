"""V1 user endpoints.

Authenticated user operations: profile, destinations, balance.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import DestinationCreateRequest, DestinationResponse, XPubResponse
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["user"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _xpub_resp(x: object) -> dict:
    return XPubResponse(
        id=x.id,
        current_balance=x.current_balance,
        next_internal_num=x.next_internal_num,
        next_external_num=x.next_external_num,
        metadata=x.metadata_,
        created_at=x.created_at,
        updated_at=x.updated_at,
    ).model_dump(mode="json")


def _dest_resp(d: object) -> dict:
    return DestinationResponse(
        id=d.id,
        xpub_id=d.xpub_id,
        locking_script=d.locking_script,
        type=d.type,
        chain=d.chain,
        num=d.num,
        address=d.address,
        metadata=d.metadata_,
        created_at=d.created_at,
        updated_at=d.updated_at,
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/xpub")
async def get_current_xpub(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get the current user's xPub record."""
    xpub = await engine.xpub_service.get_xpub_by_id(ctx.xpub_id, required=True)
    return _xpub_resp(xpub)


@router.get("/destination")
async def list_destinations(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> list[dict]:
    """List all destinations for the current user."""
    dests = await engine.destination_service.get_destinations_by_xpub(ctx.xpub_id)
    return [_dest_resp(d) for d in dests]


@router.post("/destination", status_code=201)
async def create_destination(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: DestinationCreateRequest,
) -> dict:
    """Create a new destination (address) for the current user."""
    raw_xpub = ctx.xpub
    if not raw_xpub:
        xpub_rec = await engine.xpub_service.get_xpub_by_id(ctx.xpub_id, required=True)
        raw_xpub = xpub_rec.metadata_.get("raw_xpub", "")
    dest = await engine.destination_service.new_destination(
        raw_xpub,
        metadata=body.metadata,
    )
    return _dest_resp(dest)


@router.get("/destination/{destination_id}")
async def get_destination(
    destination_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a specific destination by ID."""
    dest = await engine.destination_service.get_destination(destination_id)
    if dest is None or dest.xpub_id != ctx.xpub_id:
        from spv_wallet.engine.services.destination_service import ErrDestinationNotFound

        raise ErrDestinationNotFound
    return _dest_resp(dest)


@router.get("/utxo/balance")
async def get_balance(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get the current user's satoshi balance."""
    balance = await engine.utxo_service.get_balance(ctx.xpub_id)
    return {"xpub_id": ctx.xpub_id, "satoshis": balance}
