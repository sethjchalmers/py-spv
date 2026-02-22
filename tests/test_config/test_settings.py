"""Tests for the configuration system."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest

from spv_wallet.config.settings import (
    AppConfig,
    ARCConfig,
    ArcWaitFor,
    BHSConfig,
    CacheConfig,
    CacheEngine,
    DatabaseConfig,
    DatabaseEngine,
    MetricsConfig,
    Network,
    PaymailConfig,
    ServerConfig,
    TaskConfig,
    _load_yaml,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestDefaults:
    """Verify all default values are correct."""

    def test_server_defaults(self) -> None:
        cfg = ServerConfig()
        assert cfg.host == "0.0.0.0"  # noqa: S104
        assert cfg.port == 3003
        assert cfg.idle_timeout == 60
        assert cfg.read_timeout == 40
        assert cfg.write_timeout == 40

    def test_database_defaults(self) -> None:
        cfg = DatabaseConfig()
        assert cfg.engine == DatabaseEngine.SQLITE
        assert cfg.dsn == "sqlite+aiosqlite:///./spv_wallet.db"
        assert cfg.table_prefix == ""
        assert cfg.max_idle_connections == 5
        assert cfg.max_open_connections == 10
        assert cfg.debug_sql is False

    def test_cache_defaults(self) -> None:
        cfg = CacheConfig()
        assert cfg.engine == CacheEngine.MEMORY
        assert cfg.url == "redis://localhost:6379/0"
        assert cfg.max_connections == 10
        assert cfg.ttl_seconds == 300

    def test_arc_defaults(self) -> None:
        cfg = ARCConfig()
        assert cfg.url == "https://arc.taal.com"
        assert cfg.token == ""
        assert cfg.deployment_id == ""
        assert cfg.callback_url == ""
        assert cfg.callback_token == ""
        assert cfg.wait_for == ArcWaitFor.SEEN_ON_NETWORK

    def test_bhs_defaults(self) -> None:
        cfg = BHSConfig()
        assert cfg.url == "https://bhs.taal.com"
        assert cfg.auth_token == ""

    def test_paymail_defaults(self) -> None:
        cfg = PaymailConfig()
        assert cfg.domains == []
        assert cfg.sender_validation is True
        assert cfg.default_from_paymail == ""
        assert cfg.beef_enabled is True

    def test_metrics_defaults(self) -> None:
        cfg = MetricsConfig()
        assert cfg.enabled is True
        assert cfg.port == 9090

    def test_task_defaults(self) -> None:
        cfg = TaskConfig()
        assert cfg.enabled is True
        assert cfg.redis_url == "redis://localhost:6379/1"
        assert cfg.max_jobs == 100
        assert cfg.job_timeout == 300

    def test_app_config_defaults(self) -> None:
        cfg = AppConfig()
        assert cfg.debug is False
        assert cfg.version == "0.1.0"
        assert cfg.admin_xpub == ""
        assert cfg.encryption_key == ""
        assert cfg.config_path == ""
        # All nested configs should be defaults
        assert isinstance(cfg.server, ServerConfig)
        assert isinstance(cfg.db, DatabaseConfig)
        assert isinstance(cfg.cache, CacheConfig)
        assert isinstance(cfg.arc, ARCConfig)
        assert isinstance(cfg.bhs, BHSConfig)
        assert isinstance(cfg.paymail, PaymailConfig)
        assert isinstance(cfg.metrics, MetricsConfig)
        assert isinstance(cfg.task, TaskConfig)


# ---------------------------------------------------------------------------
# Enum validation
# ---------------------------------------------------------------------------


class TestEnums:
    """Enum fields accept only valid values."""

    def test_database_engine_postgresql(self) -> None:
        cfg = DatabaseConfig(engine=DatabaseEngine.POSTGRESQL)
        assert cfg.engine == DatabaseEngine.POSTGRESQL

    def test_database_engine_invalid(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            DatabaseConfig(engine="mysql")  # type: ignore[arg-type]

    def test_cache_engine_redis(self) -> None:
        cfg = CacheConfig(engine=CacheEngine.REDIS)
        assert cfg.engine == CacheEngine.REDIS

    def test_cache_engine_invalid(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            CacheConfig(engine="memcached")  # type: ignore[arg-type]

    def test_arc_wait_for_valid(self) -> None:
        cfg = ARCConfig(wait_for=ArcWaitFor.STORED)
        assert cfg.wait_for == ArcWaitFor.STORED

    def test_arc_wait_for_invalid(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            ARCConfig(wait_for="MINED")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Environment variable override
# ---------------------------------------------------------------------------


class TestEnvOverride:
    """Verify environment variables override defaults."""

    def test_top_level_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPVWALLET_DEBUG", "true")
        monkeypatch.setenv("SPVWALLET_ADMIN_XPUB", "xpub_from_env")
        cfg = AppConfig()
        assert cfg.debug is True
        assert cfg.admin_xpub == "xpub_from_env"

    def test_nested_env_via_delimiter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPVWALLET_SERVER__PORT", "8080")
        cfg = AppConfig()
        assert cfg.server.port == 8080

    def test_nested_db_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPVWALLET_DB__ENGINE", "postgresql")
        monkeypatch.setenv(
            "SPVWALLET_DB__DSN",
            "postgresql+asyncpg://user:pass@localhost/dbname",
        )
        cfg = AppConfig()
        assert cfg.db.engine == DatabaseEngine.POSTGRESQL
        assert "asyncpg" in cfg.db.dsn

    def test_nested_cache_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPVWALLET_CACHE__ENGINE", "redis")
        monkeypatch.setenv("SPVWALLET_CACHE__TTL_SECONDS", "600")
        cfg = AppConfig()
        assert cfg.cache.engine == CacheEngine.REDIS
        assert cfg.cache.ttl_seconds == 600

    def test_nested_arc_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPVWALLET_ARC__URL", "https://custom-arc.example.com")
        monkeypatch.setenv("SPVWALLET_ARC__TOKEN", "my-token")
        cfg = AppConfig()
        assert cfg.arc.url == "https://custom-arc.example.com"
        assert cfg.arc.token == "my-token"


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


class TestYAML:
    """YAML config file loading."""

    def test_load_yaml_nonexistent(self, tmp_path: Path) -> None:
        result = _load_yaml(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_yaml_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yaml"
        f.write_text("")
        result = _load_yaml(f)
        assert result == {}

    def test_load_yaml_valid(self, tmp_path: Path) -> None:
        f = tmp_path / "cfg.yaml"
        f.write_text(
            textwrap.dedent("""\
                debug: true
                admin_xpub: xpub_from_yaml
                server:
                  port: 9000
                db:
                  engine: postgresql
            """)
        )
        result = _load_yaml(f)
        assert result["debug"] is True
        assert result["admin_xpub"] == "xpub_from_yaml"
        assert result["server"]["port"] == 9000

    def test_load_yaml_non_dict(self, tmp_path: Path) -> None:
        """YAML file containing a list should return empty dict."""
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n")
        result = _load_yaml(f)
        assert result == {}

    def test_from_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "app.yaml"
        f.write_text(
            textwrap.dedent("""\
                debug: true
                admin_xpub: xpub_yaml
                server:
                  port: 4000
                  host: 127.0.0.1
            """)
        )
        cfg = AppConfig.from_yaml(f)
        assert cfg.debug is True
        assert cfg.admin_xpub == "xpub_yaml"
        assert cfg.server.port == 4000
        assert cfg.server.host == "127.0.0.1"

    def test_env_overrides_yaml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env vars have higher priority than YAML values."""
        f = tmp_path / "app.yaml"
        f.write_text(
            textwrap.dedent("""\
                debug: false
                admin_xpub: from_yaml
            """)
        )
        monkeypatch.setenv("SPVWALLET_ADMIN_XPUB", "from_env")
        cfg = AppConfig.from_yaml(f)
        assert cfg.admin_xpub == "from_env"


# ---------------------------------------------------------------------------
# Defaults module
# ---------------------------------------------------------------------------


class TestDefaultConstants:
    """Ensure defaults module constants are correct."""

    def test_fee_defaults(self) -> None:
        from spv_wallet.config.defaults import (
            DEFAULT_DUST_LIMIT,
            DEFAULT_FEE_BYTES,
            DEFAULT_FEE_SATOSHIS,
        )

        assert DEFAULT_FEE_SATOSHIS == 1
        assert DEFAULT_FEE_BYTES == 1000
        assert DEFAULT_DUST_LIMIT == 546


# ---------------------------------------------------------------------------
# Custom construction
# ---------------------------------------------------------------------------


class TestCustomConstruction:
    """Verify constructing with non-default values."""

    def test_explicit_nested_overrides(self) -> None:
        cfg = AppConfig(
            debug=True,
            admin_xpub="xpub_test",
            encryption_key="key123",
            server=ServerConfig(port=9999, host="127.0.0.1"),
            db=DatabaseConfig(
                engine=DatabaseEngine.POSTGRESQL,
                dsn="postgresql+asyncpg://localhost/test",
                table_prefix="app_",
            ),
            cache=CacheConfig(engine=CacheEngine.REDIS, ttl_seconds=600),
        )
        assert cfg.debug is True
        assert cfg.server.port == 9999
        assert cfg.db.engine == DatabaseEngine.POSTGRESQL
        assert cfg.db.table_prefix == "app_"
        assert cfg.cache.engine == CacheEngine.REDIS
        assert cfg.cache.ttl_seconds == 600


class TestNetwork:
    """Network enum and AppConfig.network field."""

    def test_default_is_mainnet(self) -> None:
        cfg = AppConfig()
        assert cfg.network == Network.MAINNET

    def test_set_testnet(self) -> None:
        cfg = AppConfig(network=Network.TESTNET)
        assert cfg.network == Network.TESTNET
        assert cfg.network == "testnet"

    def test_set_mainnet_string(self) -> None:
        cfg = AppConfig(network="mainnet")
        assert cfg.network == Network.MAINNET

    def test_set_testnet_string(self) -> None:
        cfg = AppConfig(network="testnet")
        assert cfg.network == Network.TESTNET

    def test_network_values(self) -> None:
        assert Network.MAINNET.value == "mainnet"
        assert Network.TESTNET.value == "testnet"
