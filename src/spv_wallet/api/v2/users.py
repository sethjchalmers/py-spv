"""V2 user endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_admin
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v2.schemas import PaginationParamsV2, UserCreateRequest, UserResponse
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-users"])


@router.post("/users", status_code=201)
async def create_user(
    body: UserCreateRequest,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> UserResponse:
    """Create a new V2 user (admin only)."""
    user = await engine.v2.users.create_user(body.pub_key)
    return UserResponse.model_validate(user)


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> UserResponse:
    """Get a V2 user by ID (admin only)."""
    user = await engine.v2.users.get_user(user_id)
    return UserResponse.model_validate(user)


@router.get("/users")
async def list_users(
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    pagination: Annotated[PaginationParamsV2, Depends()],
) -> list[UserResponse]:
    """List all V2 users (admin only)."""
    users = await engine.v2.users.list_users(
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return [UserResponse.model_validate(u) for u in users]


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    ctx: Annotated[UserContext, Depends(require_admin)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Delete a V2 user (admin only)."""
    await engine.v2.users.delete_user(user_id)
