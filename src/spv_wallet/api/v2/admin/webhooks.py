"""V2 admin webhook management — placeholder for Phase 7.

Webhook notification subscriptions will allow admins to register URLs
that receive POST callbacks when certain events occur (e.g. transaction
confirmed, contact status changed).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_admin
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-admin-webhooks"])


@router.get("/admin/webhooks")
async def list_webhooks(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> list[dict]:
    """List all registered webhooks (admin only).

    Placeholder — returns empty list until Phase 7 webhook service
    is implemented.
    """
    return []
