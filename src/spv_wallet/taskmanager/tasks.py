"""Background task definitions — cron job handlers.

Mirrors the Go cron jobs:
- ``draft_transaction_clean_up`` (60 s) — expire stale drafts
- ``sync_transaction`` (5 min) -- re-query unconfirmed txs
- ``calculate_metrics`` (15 s) — count entities for Prometheus gauges
"""

from __future__ import annotations

import logging
from datetime import UTC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spv_wallet.engine.client import SPVWalletEngine
    from spv_wallet.metrics.collector import EngineMetrics

logger = logging.getLogger(__name__)

# Cron periods (seconds) matching Go defaults
DRAFT_CLEANUP_PERIOD = 60
SYNC_TRANSACTION_PERIOD = 300  # 5 min
CALCULATE_METRICS_PERIOD = 15


async def task_cleanup_draft_transactions(engine: SPVWalletEngine) -> None:
    """Delete draft transactions that have passed their ``expires_at``.

    Mirrors Go ``taskCleanupDraftTransactions``.
    """
    try:
        from datetime import datetime

        from sqlalchemy import delete

        from spv_wallet.engine.models.draft_transaction import DraftTransaction

        async with engine.datastore.session() as session:
            now = datetime.now(tz=UTC).isoformat()
            stmt = delete(DraftTransaction).where(
                DraftTransaction.status == "draft",
                DraftTransaction.expires_at.isnot(None),
                DraftTransaction.expires_at < now,
            )
            result = await session.execute(stmt)
            await session.commit()
            count = result.rowcount  # type: ignore[union-attr]
            if count:
                logger.info("Cleaned up %d expired draft transactions", count)
    except Exception:
        logger.exception("draft_transaction_clean_up failed")


async def task_sync_transactions(engine: SPVWalletEngine) -> None:
    """Re-query ARC for transactions that are still unconfirmed.

    Mirrors Go ``taskSyncTransactions``.
    """
    try:
        chain = engine.chain_service
        if chain is None:
            return

        from sqlalchemy import select

        from spv_wallet.engine.models.transaction import Transaction

        async with engine.datastore.session() as session:
            stmt = select(Transaction).where(
                Transaction.tx_status.in_(["broadcasted", "seen_on_network"]),
            )
            result = await session.execute(stmt)
            txs = result.scalars().all()

        for tx in txs:
            try:
                info = await chain.query_transaction(tx.id)
                if info and info.tx_status and info.tx_status != tx.tx_status:
                    async with engine.datastore.session() as session:
                        tx_record = await session.get(Transaction, tx.id)
                        if tx_record:
                            tx_record.tx_status = info.tx_status
                            if info.block_hash:
                                tx_record.block_hash = info.block_hash
                            if info.block_height:
                                tx_record.block_height = info.block_height
                            await session.commit()
                            logger.debug("Synced tx %s → %s", tx.id[:16], info.tx_status)
            except Exception:
                logger.debug("Failed to sync tx %s", tx.id[:16])
    except Exception:
        logger.exception("sync_transactions failed")


async def task_calculate_metrics(engine: SPVWalletEngine, metrics: EngineMetrics) -> None:
    """Count entities and push to Prometheus gauges.

    Mirrors Go ``taskCalculateMetrics``.
    """
    try:
        from sqlalchemy import func, select

        from spv_wallet.engine.models.access_key import AccessKey
        from spv_wallet.engine.models.destination import Destination
        from spv_wallet.engine.models.paymail_address import PaymailAddress
        from spv_wallet.engine.models.utxo import UTXO
        from spv_wallet.engine.models.xpub import Xpub

        async with engine.datastore.session() as session:
            xpub_count = (await session.execute(select(func.count(Xpub.id)))).scalar() or 0
            utxo_count = (await session.execute(select(func.count(UTXO.id)))).scalar() or 0
            paymail_count = (
                await session.execute(select(func.count(PaymailAddress.id)))
            ).scalar() or 0
            dest_count = (await session.execute(select(func.count(Destination.id)))).scalar() or 0
            ak_count = (await session.execute(select(func.count(AccessKey.id)))).scalar() or 0

        metrics.set_xpub_count(xpub_count)
        metrics.set_utxo_count(utxo_count)
        metrics.set_paymail_count(paymail_count)
        metrics.set_destination_count(dest_count)
        metrics.set_access_key_count(ak_count)
    except Exception:
        logger.exception("calculate_metrics failed")
