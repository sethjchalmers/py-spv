"""Task manager — background job processing and cron scheduling.

Provides ``TaskManager`` for periodic background tasks such as:
- Draft transaction cleanup (expired drafts)
- Unconfirmed transaction sync (re-query ARC)
- Metrics calculation (entity counts for Prometheus gauges)

Uses ``asyncio`` tasks for scheduling. For distributed deployments,
Redis ``SET NX`` provides distributed locking so only one instance
runs a given cron job at a time.
"""

from __future__ import annotations

from spv_wallet.taskmanager.manager import TaskManager

__all__ = ["TaskManager"]
