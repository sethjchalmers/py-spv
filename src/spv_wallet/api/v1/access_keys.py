"""V1 access key endpoints.

User-facing access key creation, listing, and revocation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import AccessKeyCreateResponse, AccessKeyResponse
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001
from spv_wallet.engine.services.access_key_service import ErrAccessKeyNotFound

router = APIRouter(tags=["access_key"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ak_resp(ak: object) -> dict:
    return AccessKeyResponse(
        id=ak.id,
        xpub_id=ak.xpub_id,
        key=ak.key,
        metadata=ak.metadata_,
        created_at=ak.created_at,
        deleted_at=ak.deleted_at,
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/access-key", status_code=201)
async def create_access_key(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Create a new access key for the current user."""
    ak, private_key_hex = await engine.access_key_service.new_access_key(
        ctx.xpub_id,
    )
    return AccessKeyCreateResponse(
        id=ak.id,
        xpub_id=ak.xpub_id,
        key=ak.key,
        private_key=private_key_hex,
        metadata=ak.metadata_,
        created_at=ak.created_at,
    ).model_dump(mode="json")


@router.get("/access-key")
async def list_access_keys(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> list[dict]:
    """List all access keys for the current user."""
    keys = await engine.access_key_service.get_access_keys_by_xpub(ctx.xpub_id)
    return [_ak_resp(k) for k in keys]


@router.get("/access-key/count")
async def count_access_keys(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Count access keys for the current user."""
    count = await engine.access_key_service.count_access_keys(ctx.xpub_id)
    return {"count": count}


@router.get("/access-key/{key_id}")
async def get_access_key(
    key_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a specific access key by ID."""
    ak = await engine.access_key_service.get_access_key(key_id)
    if ak is None or ak.xpub_id != ctx.xpub_id:
        raise ErrAccessKeyNotFound
    return _ak_resp(ak)


@router.delete("/access-key/{key_id}", status_code=204)
async def revoke_access_key(
    key_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Revoke an access key."""
    ak = await engine.access_key_service.get_access_key(key_id)
    if ak is None or ak.xpub_id != ctx.xpub_id:
        raise ErrAccessKeyNotFound

    await engine.access_key_service.revoke_access_key(key_id)
