"""V1 Merkle root endpoints.

Placeholder for Merkle root verification endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["merkleroots"])


@router.get("/merkleroots")
async def get_merkle_roots() -> dict:
    """Get Merkle roots — placeholder endpoint."""
    return {"message": "merkle root verification not yet implemented"}
