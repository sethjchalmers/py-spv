"""V2 contact endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from spv_wallet.api.dependencies import get_engine, require_user
from spv_wallet.api.middleware.auth import UserContext  # noqa: TC001
from spv_wallet.api.v2.schemas import (
    ContactCreateRequestV2,
    ContactResponseV2,
    ContactStatusUpdateV2,
    PaginationParamsV2,
)
from spv_wallet.engine.client import SPVWalletEngine  # noqa: TC001

router = APIRouter(tags=["v2-contacts"])


@router.post("/contacts", status_code=201)
async def create_contact(
    body: ContactCreateRequestV2,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> ContactResponseV2:
    """Create a new contact for the authenticated user."""
    contact = await engine.v2.contacts.create_contact(
        ctx.xpub_id,
        full_name=body.full_name,
        paymail=body.paymail,
        pub_key=body.pub_key,
    )
    return ContactResponseV2.model_validate(contact)


@router.get("/contacts")
async def list_contacts(
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
    pagination: Annotated[PaginationParamsV2, Depends()],
    status: str | None = None,
) -> list[ContactResponseV2]:
    """List contacts for the authenticated user."""
    contacts = await engine.v2.contacts.list_for_user(
        ctx.xpub_id,
        status=status,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return [ContactResponseV2.model_validate(c) for c in contacts]


@router.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: int,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> ContactResponseV2:
    """Get a contact by ID."""
    contact = await engine.v2.contacts.get_contact(contact_id)
    return ContactResponseV2.model_validate(contact)


@router.patch("/contacts/{contact_id}/status")
async def update_contact_status(
    contact_id: int,
    body: ContactStatusUpdateV2,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> ContactResponseV2:
    """Update a contact's status."""
    contact = await engine.v2.contacts.update_status(contact_id, body.status)
    return ContactResponseV2.model_validate(contact)


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: int,
    ctx: Annotated[UserContext, Depends(require_user)],
    engine: Annotated[SPVWalletEngine, Depends(get_engine)],
) -> None:
    """Delete a contact."""
    await engine.v2.contacts.delete_contact(contact_id)
