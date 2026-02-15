"""CORS middleware configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.middleware.cors import CORSMiddleware

from spv_wallet.api.middleware.auth import (
    AUTH_HEADER_ACCESS_KEY,
    AUTH_HEADER_HASH,
    AUTH_HEADER_NONCE,
    AUTH_HEADER_SIGNATURE,
    AUTH_HEADER_TIME,
    AUTH_HEADER_XPUB,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

# All custom auth headers that the browser needs to send via CORS pre-flight.
_AUTH_HEADERS = [
    AUTH_HEADER_XPUB,
    AUTH_HEADER_ACCESS_KEY,
    AUTH_HEADER_SIGNATURE,
    AUTH_HEADER_HASH,
    AUTH_HEADER_NONCE,
    AUTH_HEADER_TIME,
]


def setup_cors(app: FastAPI) -> None:
    """Add CORS middleware allowing all origins + auth headers.

    Mirrors the Go server which permits ``*`` origins and exposes the custom
    ``x-auth-*`` headers.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", *_AUTH_HEADERS],
        expose_headers=_AUTH_HEADERS,
    )
