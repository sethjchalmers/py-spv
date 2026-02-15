"""V1 contact endpoints.

User-facing contact CRUD and status updates.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v1.schemas import (
    ContactCreateRequest,
    ContactResponse,
    ContactUpdateStatusRequest,
)
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001
from spv_wallet.errors.definitions import ErrContactNotFound

router = APIRouter(tags=["contact"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _contact_resp(c: object) -> dict:
    return ContactResponse(
        id=c.id,
        xpub_id=c.xpub_id,
        full_name=c.full_name,
        paymail=c.paymail,
        pub_key=c.pub_key,
        status=c.status,
        metadata=c.metadata_,
        created_at=c.created_at,
        updated_at=c.updated_at,
    ).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/contact", status_code=201)
async def create_contact(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: ContactCreateRequest,
) -> dict:
    """Create a new contact."""
    contact = await engine.contact_service.create_contact(
        ctx.xpub_id,
        body.paymail,
        full_name=body.full_name,
        metadata=body.metadata,
    )
    return _contact_resp(contact)


@router.get("/contact")
async def list_contacts(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    status: str | None = None,
    paymail: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Search contacts for the current user."""
    contacts = await engine.contact_service.search_contacts(
        xpub_id=ctx.xpub_id,
        status=status,
        paymail=paymail,
        limit=limit,
        offset=offset,
    )
    return [_contact_resp(c) for c in contacts]


@router.get("/contact/{contact_id}")
async def get_contact(
    contact_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> dict:
    """Get a specific contact by ID."""
    contact = await engine.contact_service.get_contact(contact_id)
    if contact is None or contact.xpub_id != ctx.xpub_id:
        raise ErrContactNotFound
    return _contact_resp(contact)


@router.patch("/contact/{contact_id}/status")
async def update_contact_status(
    contact_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    body: ContactUpdateStatusRequest,
) -> dict:
    """Update a contact's status (confirm, reject, etc.)."""
    # Verify ownership first
    contact = await engine.contact_service.get_contact(contact_id)
    if contact is None or contact.xpub_id != ctx.xpub_id:
        raise ErrContactNotFound

    updated = await engine.contact_service.update_status(contact_id, body.status)
    return _contact_resp(updated)


@router.delete("/contact/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: str,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Delete a contact."""
    contact = await engine.contact_service.get_contact(contact_id)
    if contact is None or contact.xpub_id != ctx.xpub_id:
        raise ErrContactNotFound

    await engine.contact_service.delete_contact(contact_id)
