"""Notifications — event emission and webhook dispatch.

Provides:
- ``NotificationService`` — fan-out event bus using asyncio queues
- ``WebhookNotifier`` — delivers events to a single webhook URL with retries
- ``WebhookManager`` — manages lifecycle of all webhook notifiers
"""

from __future__ import annotations

from spv_wallet.notifications.events import RawEvent, TransactionEvent
from spv_wallet.notifications.service import NotificationService
from spv_wallet.notifications.webhook import WebhookManager, WebhookNotifier

__all__ = [
    "NotificationService",
    "RawEvent",
    "TransactionEvent",
    "WebhookManager",
    "WebhookNotifier",
]
