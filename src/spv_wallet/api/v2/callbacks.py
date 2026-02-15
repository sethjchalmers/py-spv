"""V2 ARC broadcast callback handler."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine
from spv_wallet.api.v2.schemas import ArcCallbackRequestV2  # noqa: TC001
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-callbacks"])


@router.post("/transactions/broadcast/callback", status_code=200)
async def arc_callback(
    body: ArcCallbackRequestV2,
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict[str, str]:
    """Handle ARC broadcast callback for V2 transactions.

    This endpoint is called directly by ARC — no user authentication required.
    """
    await engine.v2.tx_sync.handle_arc_callback(
        body.txid,
        body.tx_status,
        block_height=body.block_height,
        block_hash=body.block_hash,
        merkle_path=body.merkle_path,
    )
    return {"status": "ok"}
