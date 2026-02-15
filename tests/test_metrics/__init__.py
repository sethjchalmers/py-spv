"""Tests for metrics module — MetricsCollector and EngineMetrics."""

from __future__ import annotations

from prometheus_client import CollectorRegistry

from spv_wallet.metrics.collector import EngineMetrics, MetricsCollector


class TestMetricsCollector:
    """Tests for the low-level MetricsCollector."""

    def test_creates_registry(self) -> None:
        c = MetricsCollector()
        assert c.registry is not None

    def test_custom_registry(self) -> None:
        reg = CollectorRegistry()
        c = MetricsCollector(registry=reg)
        assert c.registry is reg

    def test_gauge(self) -> None:
        reg = CollectorRegistry()
        c = MetricsCollector(registry=reg)
        g = c.gauge("test_gauge", "A test gauge")
        g.set(42)
        assert g._value.get() == 42.0

    def test_histogram(self) -> None:
        reg = CollectorRegistry()
        c = MetricsCollector(registry=reg)
        h = c.histogram("test_hist", "A test histogram")
        h.observe(0.5)
        # Histogram sum should be 0.5
        assert h._sum.get() == 0.5

    def test_counter(self) -> None:
        reg = CollectorRegistry()
        c = MetricsCollector(registry=reg)
        ct = c.counter("test_counter", "A test counter")
        ct.inc()
        ct.inc(2)
        assert ct._value.get() == 3.0


class TestEngineMetrics:
    """Tests for the high-level EngineMetrics."""

    def test_set_xpub_count(self) -> None:
        m = EngineMetrics()
        m.set_xpub_count(10)
        # No error means the gauge was set successfully

    def test_set_utxo_count(self) -> None:
        m = EngineMetrics()
        m.set_utxo_count(100)

    def test_set_paymail_count(self) -> None:
        m = EngineMetrics()
        m.set_paymail_count(5)

    def test_set_destination_count(self) -> None:
        m = EngineMetrics()
        m.set_destination_count(50)

    def test_set_access_key_count(self) -> None:
        m = EngineMetrics()
        m.set_access_key_count(3)

    def test_track_record_transaction(self) -> None:
        m = EngineMetrics()
        with m.track_record_transaction():
            pass  # Simulates a fast operation

    def test_track_query_transaction(self) -> None:
        m = EngineMetrics()
        with m.track_query_transaction():
            pass

    def test_track_verify_merkle_roots(self) -> None:
        m = EngineMetrics()
        with m.track_verify_merkle_roots():
            pass

    def test_track_add_contact(self) -> None:
        m = EngineMetrics()
        with m.track_add_contact():
            pass

    def test_track_cron(self) -> None:
        m = EngineMetrics()
        with m.track_cron("test_job"):
            pass

    def test_registry_property(self) -> None:
        m = EngineMetrics()
        assert m.registry is not None
