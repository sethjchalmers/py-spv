"""Metrics collector — Prometheus counters, gauges, histograms.

Mirrors the Go ``engine/metrics/`` package:
- ``bsv_stats_total`` gauge-vec  (xpubs, utxos, paymails, destinations, access_keys)
- ``bsv_record_transaction_histogram``
- ``bsv_query_transaction_histogram``
- ``bsv_verify_merkle_roots_histogram``
- ``bsv_add_contact_histogram``
- ``bsv_cron_histogram``
- ``bsv_cron_last_execution_gauge``
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

if TYPE_CHECKING:
    from collections.abc import Iterator


# Metric name prefix matching Go implementation
_PREFIX = "bsv"

# Labels for the stats gauge
_STAT_LABELS = ("entity",)
_STAT_ENTITIES = (
    "xpubs",
    "utxos",
    "paymails",
    "destinations",
    "access_keys",
)


class MetricsCollector:
    """Low-level Prometheus collector that owns the registry.

    Use :class:`EngineMetrics` for the high-level tracking interface.
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._registry = registry or CollectorRegistry()

    @property
    def registry(self) -> CollectorRegistry:
        """Return the underlying Prometheus registry."""
        return self._registry

    def gauge(self, name: str, doc: str, labels: tuple[str, ...] = ()) -> Gauge:
        """Register and return a Gauge."""
        return Gauge(name, doc, labels, registry=self._registry)

    def histogram(self, name: str, doc: str, labels: tuple[str, ...] = ()) -> Histogram:
        """Register and return a Histogram."""
        return Histogram(name, doc, labels, registry=self._registry)

    def counter(self, name: str, doc: str, labels: tuple[str, ...] = ()) -> Counter:
        """Register and return a Counter."""
        return Counter(name, doc, labels, registry=self._registry)


class EngineMetrics:
    """High-level engine metrics matching Go ``engine/metrics.Metrics``.

    All histograms track operation duration in seconds.
    """

    def __init__(self, collector: MetricsCollector | None = None) -> None:
        self._collector = collector or MetricsCollector()

        # Stats gauge — entity counts (xpubs, utxos, etc.)
        self._stats = self._collector.gauge(
            f"{_PREFIX}_stats_total",
            "Entity counts in the SPV wallet engine",
            _STAT_LABELS,
        )

        # Operation histograms
        self._record_tx = self._collector.histogram(
            f"{_PREFIX}_record_transaction_histogram",
            "Duration of transaction recording operations",
        )
        self._query_tx = self._collector.histogram(
            f"{_PREFIX}_query_transaction_histogram",
            "Duration of transaction query operations",
        )
        self._verify_merkle = self._collector.histogram(
            f"{_PREFIX}_verify_merkle_roots_histogram",
            "Duration of Merkle root verification operations",
        )
        self._add_contact = self._collector.histogram(
            f"{_PREFIX}_add_contact_histogram",
            "Duration of add contact operations",
        )

        # Cron metrics
        self._cron_histogram = self._collector.histogram(
            f"{_PREFIX}_cron_histogram",
            "Duration of cron job executions",
            ("job_name",),
        )
        self._cron_last = self._collector.gauge(
            f"{_PREFIX}_cron_last_execution_gauge",
            "Timestamp of last cron execution",
            ("job_name",),
        )

    @property
    def registry(self) -> CollectorRegistry:
        """Return the underlying Prometheus registry."""
        return self._collector.registry

    # -- Stat setters --

    def set_xpub_count(self, count: int) -> None:
        """Set the current number of registered xPubs."""
        self._stats.labels(entity="xpubs").set(count)

    def set_utxo_count(self, count: int) -> None:
        """Set the current number of UTXOs."""
        self._stats.labels(entity="utxos").set(count)

    def set_paymail_count(self, count: int) -> None:
        """Set the current number of paymail addresses."""
        self._stats.labels(entity="paymails").set(count)

    def set_destination_count(self, count: int) -> None:
        """Set the current number of destinations."""
        self._stats.labels(entity="destinations").set(count)

    def set_access_key_count(self, count: int) -> None:
        """Set the current number of access keys."""
        self._stats.labels(entity="access_keys").set(count)

    # -- Operation trackers (context managers) --

    @contextmanager
    def track_record_transaction(self) -> Iterator[None]:
        """Track the duration of a transaction recording."""
        start = time.monotonic()
        try:
            yield
        finally:
            self._record_tx.observe(time.monotonic() - start)

    @contextmanager
    def track_query_transaction(self) -> Iterator[None]:
        """Track the duration of a transaction query."""
        start = time.monotonic()
        try:
            yield
        finally:
            self._query_tx.observe(time.monotonic() - start)

    @contextmanager
    def track_verify_merkle_roots(self) -> Iterator[None]:
        """Track the duration of Merkle root verification."""
        start = time.monotonic()
        try:
            yield
        finally:
            self._verify_merkle.observe(time.monotonic() - start)

    @contextmanager
    def track_add_contact(self) -> Iterator[None]:
        """Track the duration of an add-contact operation."""
        start = time.monotonic()
        try:
            yield
        finally:
            self._add_contact.observe(time.monotonic() - start)

    @contextmanager
    def track_cron(self, job_name: str) -> Iterator[None]:
        """Track the duration of a cron job and record last execution time."""
        start = time.monotonic()
        try:
            yield
        finally:
            self._cron_histogram.labels(job_name=job_name).observe(time.monotonic() - start)
            self._cron_last.labels(job_name=job_name).set(time.time())
