"""Event types for the notification system.

Mirrors Go ``engine/notifications/events.go``:
- ``RawEvent`` — envelope with type string + JSON content
- ``TransactionEvent`` — transaction state change
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawEvent:
    """Generic event envelope sent to subscribers."""

    type: str
    content: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return asdict(self)


@dataclass(frozen=True)
class TransactionEvent(RawEvent):
    """Event emitted when a transaction changes state."""

    type: str = "transaction"
    transaction_id: str = ""
    xpub_id: str = ""
    status: str = ""
    value: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (includes all fields)."""
        return asdict(self)
