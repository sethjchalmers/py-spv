"""FastAPI dependency injection helpers.

Provides ``Depends()``-compatible callables for engine access and
authentication in route handlers.

Usage in a route::

    @router.get("/me")
    async def get_me(
        ctx: UserContext = Depends(require_user),
        engine: SPVWalletEngine = Depends(get_engine),
    ) -> ...:
        ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request

from spv_wallet.api.middleware.auth import (
    AUTH_HEADER_ACCESS_KEY,
    AUTH_HEADER_XPUB,
    UserContext,
    authenticate_request,
)
from spv_wallet.api.middleware.auth import (
    require_admin as _require_admin,
)
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001
from spv_wallet.errors.definitions import ErrUnauthorized

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def get_engine(request: Request) -> SPVWalletEngine:
    """Retrieve the engine from ``app.state``.

    The engine is stored on ``app.state.engine`` during lifespan startup.

    Raises:
        ErrUnauthorized: If the engine is not initialized (should never happen
        after startup).
    """
    engine: SPVWalletEngine | None = getattr(request.app.state, "engine", None)
    if engine is None:
        raise ErrUnauthorized
    return engine


# ---------------------------------------------------------------------------
# Auth context
# ---------------------------------------------------------------------------


async def get_user_context(
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    x_auth_xpub: Annotated[str, Header(alias=AUTH_HEADER_XPUB)] = "",
    x_auth_key: Annotated[str, Header(alias=AUTH_HEADER_ACCESS_KEY)] = "",
) -> UserContext:
    """Resolve the authenticated user context from request headers.

    At least one of ``x-auth-xpub`` or ``x-auth-key`` must be provided.
    """
    return await authenticate_request(
        engine,
        xpub_header=x_auth_xpub,
        access_key_header=x_auth_key,
    )


def require_user(
    ctx: Annotated[UserContext, Depends(get_user_context)],
) -> UserContext:
    """Dependency that requires any valid authentication (user or admin)."""
    return ctx


def require_admin(
    ctx: Annotated[UserContext, Depends(get_user_context)],
) -> UserContext:
    """Dependency that requires admin authentication.

    Raises:
        SPVError: 403 if the user is not an admin.
    """
    _require_admin(ctx)
    return ctx
