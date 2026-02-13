"""Application entry point for the SPV Wallet server."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Start the SPV Wallet server."""
    uvicorn.run(
        "spv_wallet.api.app:create_app",
        factory=True,
        host="0.0.0.0",  # noqa: S104
        port=3003,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
