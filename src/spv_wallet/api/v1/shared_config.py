"""V1 shared config endpoint.

Returns public configuration for wallet clients.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import SharedConfigResponse
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["config"])


@router.get("/shared-config")
async def get_shared_config(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Return public wallet configuration for the authenticated client."""
    domains: list[str] = []
    if engine.config.paymail and engine.config.paymail.default_domain:
        domains.append(engine.config.paymail.default_domain)

    return SharedConfigResponse(
        paymail_domains=domains,
        experimental_features={},
    ).model_dump(mode="json")
