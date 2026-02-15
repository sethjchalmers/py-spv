"""V2 admin webhook management.

Webhook notification subscriptions allow admins to register URLs
that receive POST callbacks when certain events occur (e.g. transaction
confirmed, contact status changed).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from spv_wallet.api.dependencies import get_engine, require_admin
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-admin-webhooks"])


class WebhookSubscribeRequest(BaseModel):
    """Request body for subscribing a webhook."""

    url: str
    token_header: str = "Authorization"  # noqa: S105
    token_value: str = ""


class WebhookUnsubscribeRequest(BaseModel):
    """Request body for unsubscribing a webhook."""

    url: str


@router.get("/admin/webhooks")
async def list_webhooks(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> list[dict]:
    """List all registered webhooks (admin only)."""
    mgr = engine.webhook_manager
    if mgr is None:
        return []
    return mgr.get_all()


@router.post("/admin/webhooks", status_code=201)
async def subscribe_webhook(
    body: WebhookSubscribeRequest,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict[str, str]:
    """Subscribe a new webhook URL (admin only)."""
    mgr = engine.webhook_manager
    if mgr is None:
        raise HTTPException(status_code=503, detail="Notifications not enabled")
    await mgr.subscribe(body.url, body.token_header, body.token_value)
    return {"url": body.url, "status": "subscribed"}


@router.delete("/admin/webhooks")
async def unsubscribe_webhook(
    body: WebhookUnsubscribeRequest,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict[str, str]:
    """Unsubscribe a webhook URL (admin only)."""
    mgr = engine.webhook_manager
    if mgr is None:
        raise HTTPException(status_code=503, detail="Notifications not enabled")
    await mgr.unsubscribe(body.url)
    return {"url": body.url, "status": "unsubscribed"}
