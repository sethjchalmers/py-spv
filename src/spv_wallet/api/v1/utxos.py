"""V1 UTXO endpoints.

User-facing UTXO queries.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import UTXOResponse
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["utxo"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utxo_resp(u: object) -> dict:
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/utxo")
async def list_utxos(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    unspent_only: bool = False,
) -> list[dict]:
    """List UTXOs for the current user."""
    utxos = await engine.utxo_service.get_utxos(
        xpub_id=ctx.xpub_id,
        unspent_only=unspent_only,
    )
    return [_utxo_resp(u) for u in utxos]


@router.get("/utxo/count")
async def count_utxos(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    unspent_only: bool = False,
) -> dict:
    """Count UTXOs for the current user."""
    count = await engine.utxo_service.count_utxos(
        xpub_id=ctx.xpub_id,
        unspent_only=unspent_only,
    )
    return {"count": count}


@router.get("/utxo/{utxo_id}")
async def get_utxo(
    utxo_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a specific UTXO by ID."""
    from spv_wallet.errors.definitions import ErrUTXONotFound

    utxo = await engine.utxo_service.get_utxo(utxo_id)
    if utxo is None or utxo.xpub_id != ctx.xpub_id:
        raise ErrUTXONotFound
    return _utxo_resp(utxo)
