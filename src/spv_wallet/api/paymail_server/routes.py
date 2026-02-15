"""Paymail server HTTP routes.

Implements the BSV Alias (paymail) protocol endpoints:
- GET  /.well-known/bsvalias              — Capability discovery
- GET  /v1/bsvalias/id/{alias}@{domain}   — PKI (public key)
- POST /v1/bsvalias/p2p-payment-destination/{alias}@{domain} — P2P destinations
- POST /v1/bsvalias/receive-transaction/{alias}@{domain}     — Receive P2P tx

Mirrors the Go ``actions/paymail/`` route handlers.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from spv_wallet.errors.spv_errors import SPVError
from spv_wallet.paymail.models import (
    BRFC_BEEF,
    BRFC_P2P_PAYMENT_DESTINATION,
    BRFC_P2P_SEND_TRANSACTION,
    BRFC_PIKE_INVITE,
    BRFC_PIKE_OUTPUTS,
    BRFC_PKI,
    BRFC_PUBLIC_PROFILE,
    BRFC_SENDER_VALIDATION,
    BRFC_VERIFY_PUBLIC_KEY,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["paymail"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class P2PDestinationRequest(BaseModel):
    """Request body for P2P payment destination."""

    satoshis: int


class P2PReceiveRequest(BaseModel):
    """Request body for receiving a P2P transaction."""

    hex: str = ""
    reference: str = ""
    beef: str = ""
    metadata: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/.well-known/bsvalias")
async def capabilities(request: Request) -> dict:
    """BSV Alias capability discovery document.

    Returns the list of supported paymail capabilities
    and their URL templates.
    """
    base_url = str(request.base_url).rstrip("/")
    at = "{alias}@{domain.tld}"
    pk = f"{at}/{{pubkey}}"

    return {
        "bsvalias": "1.0",
        "capabilities": {
            BRFC_PKI: f"{base_url}/v1/bsvalias/id/{at}",
            BRFC_SENDER_VALIDATION: (f"{base_url}/v1/bsvalias/sender-validation/{at}"),
            BRFC_VERIFY_PUBLIC_KEY: (f"{base_url}/v1/bsvalias/verify-pubkey/{pk}"),
            BRFC_PUBLIC_PROFILE: (f"{base_url}/v1/bsvalias/public-profile/{at}"),
            BRFC_P2P_PAYMENT_DESTINATION: (f"{base_url}/v1/bsvalias/p2p-payment-destination/{at}"),
            BRFC_P2P_SEND_TRANSACTION: (f"{base_url}/v1/bsvalias/receive-transaction/{at}"),
            BRFC_BEEF: f"{base_url}/v1/bsvalias/beef/{at}",
            BRFC_PIKE_INVITE: (f"{base_url}/v1/bsvalias/pike/invite/{at}"),
            BRFC_PIKE_OUTPUTS: (f"{base_url}/v1/bsvalias/pike/outputs/{at}"),
        },
    }


@router.get("/v1/bsvalias/id/{alias}@{domain}")
async def pki(request: Request, alias: str, domain: str) -> dict:
    """Public Key Infrastructure — resolve public key for a paymail.

    Args:
        request: The incoming request.
        alias: Paymail alias (local part).
        domain: Paymail domain.

    Returns:
        PKI response with bsvalias version, handle, and public key.
    """
    provider = _get_provider(request)
    try:
        paymail = await provider.get_paymail_by_alias(alias, domain)
    except SPVError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    # The public key would come from the xPub's derived key
    # For now, return a placeholder derived from the xpub_id
    return {
        "bsvalias": "1.0",
        "handle": f"{alias}@{domain}",
        "pubkey": paymail.xpub_id[:66],  # Truncated placeholder
    }


@router.post("/v1/bsvalias/p2p-payment-destination/{alias}@{domain}")
async def p2p_destination(
    request: Request,
    alias: str,
    domain: str,
    body: P2PDestinationRequest,
) -> dict:
    """P2P payment destination — provide outputs for incoming payment.

    Args:
        request: The incoming request.
        alias: Recipient's alias.
        domain: Recipient's domain.
        body: Request with satoshis amount.

    Returns:
        P2P destination response with outputs and reference.
    """
    provider = _get_provider(request)
    try:
        return await provider.create_p2p_destination_response(alias, domain, body.satoshis)
    except SPVError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/v1/bsvalias/receive-transaction/{alias}@{domain}")
async def receive_transaction(
    request: Request,
    alias: str,
    domain: str,
    body: P2PReceiveRequest,
) -> dict:
    """Receive a P2P transaction from a sender.

    Args:
        request: The incoming request.
        alias: Recipient's alias.
        domain: Recipient's domain.
        body: Transaction payload.

    Returns:
        Response with txid and note.
    """
    provider = _get_provider(request)
    try:
        return await provider.record_transaction(
            alias,
            domain,
            hex=body.hex,
            reference=body.reference,
            beef=body.beef,
            metadata=body.metadata,
        )
    except SPVError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/v1/bsvalias/public-profile/{alias}@{domain}")
async def public_profile(request: Request, alias: str, domain: str) -> dict:
    """Public profile for a paymail address.

    Args:
        request: The incoming request.
        alias: Paymail alias.
        domain: Paymail domain.

    Returns:
        Profile with name and avatar.
    """
    provider = _get_provider(request)
    try:
        paymail = await provider.get_paymail_by_alias(alias, domain)
    except SPVError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return {
        "name": paymail.public_name,
        "avatar": paymail.avatar,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_provider(request: Request):
    """Get the PaymailServiceProvider from the app state.

    Args:
        request: The incoming FastAPI request.

    Returns:
        The PaymailServiceProvider instance.
    """
    from spv_wallet.api.paymail_server.provider import PaymailServiceProvider

    provider = getattr(request.app.state, "paymail_provider", None)
    if provider is None:
        # Create on first access (lazy init for testing)
        engine = getattr(request.app.state, "engine", None)
        if engine is None:
            raise HTTPException(status_code=503, detail="Engine not initialized")
        provider = PaymailServiceProvider(engine)
        request.app.state.paymail_provider = provider
    return provider
