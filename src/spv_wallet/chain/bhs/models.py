"""BHS data models — MerkleRootConfirmation, ConfirmationState.

Data classes representing Block Headers Service API objects.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Confirmation state enum
# ---------------------------------------------------------------------------


class ConfirmationState(enum.StrEnum):
    """BHS Merkle root verification states."""

    CONFIRMED = "CONFIRMED"
    INVALID = "INVALID"
    UNABLE_TO_VERIFY = "UNABLE_TO_VERIFY"

    @classmethod
    def from_string(cls, value: str) -> ConfirmationState:
        """Parse a state string, returning UNABLE_TO_VERIFY for unrecognised values."""
        try:
            return cls(value.upper())
        except ValueError:
            return cls.UNABLE_TO_VERIFY


# ---------------------------------------------------------------------------
# Merkle root verification request/response
# ---------------------------------------------------------------------------


@dataclass
class MerkleRootVerification:
    """A single Merkle root to verify against BHS.

    Attributes:
        merkle_root: The Merkle root hash (hex).
        block_height: The block height containing this root.
    """

    merkle_root: str
    block_height: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to BHS request format."""
        return {
            "merkleRoot": self.merkle_root,
            "blockHeight": self.block_height,
        }


@dataclass
class MerkleRootConfirmation:
    """Result of a Merkle root verification from BHS.

    Attributes:
        merkle_root: The Merkle root hash (hex).
        block_height: The block height.
        confirmation: The confirmation state.
    """

    merkle_root: str = ""
    block_height: int = 0
    confirmation: ConfirmationState = ConfirmationState.UNABLE_TO_VERIFY

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MerkleRootConfirmation:
        """Create from BHS JSON response."""
        return cls(
            merkle_root=data.get("merkleRoot", data.get("merkle_root", "")),
            block_height=data.get("blockHeight", data.get("block_height", 0)),
            confirmation=ConfirmationState.from_string(
                data.get("confirmation", data.get("confirmationState", "UNABLE_TO_VERIFY"))
            ),
        )


# ---------------------------------------------------------------------------
# Paginated Merkle roots response
# ---------------------------------------------------------------------------


@dataclass
class MerkleRootsResponse:
    """Paginated response from GET /api/v1/chain/merkleroot.

    Attributes:
        content: List of Merkle root confirmations.
        page: Current page number.
        total_pages: Total number of pages.
        total_elements: Total number of elements.
    """

    content: list[MerkleRootConfirmation] = field(default_factory=list)
    page: int = 0
    total_pages: int = 0
    total_elements: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MerkleRootsResponse:
        """Create from BHS JSON response."""
        content_list = data.get("content", [])
        page_data = data.get("page", {})
        return cls(
            content=[MerkleRootConfirmation.from_dict(item) for item in content_list],
            page=page_data.get("number", data.get("page", 0))
            if isinstance(page_data, dict)
            else data.get("page", 0),
            total_pages=page_data.get("totalPages", data.get("totalPages", 0))
            if isinstance(page_data, dict)
            else data.get("totalPages", 0),
            total_elements=page_data.get("totalElements", data.get("totalElements", 0))
            if isinstance(page_data, dict)
            else data.get("totalElements", 0),
        )


@dataclass
class VerifyMerkleRootsResponse:
    """Response from POST /api/v1/chain/merkleroot/verify.

    Attributes:
        confirmation_state: Overall confirmation state.
        confirmations: Individual confirmations per root.
    """

    confirmation_state: ConfirmationState = ConfirmationState.UNABLE_TO_VERIFY
    confirmations: list[MerkleRootConfirmation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerifyMerkleRootsResponse:
        """Create from BHS JSON response."""
        state = data.get("confirmationState", data.get("confirmation_state", "UNABLE_TO_VERIFY"))
        confirmations = [MerkleRootConfirmation.from_dict(c) for c in data.get("confirmations", [])]
        return cls(
            confirmation_state=ConfirmationState.from_string(state),
            confirmations=confirmations,
        )

    @property
    def all_confirmed(self) -> bool:
        """Check if all roots were confirmed."""
        return self.confirmation_state == ConfirmationState.CONFIRMED
