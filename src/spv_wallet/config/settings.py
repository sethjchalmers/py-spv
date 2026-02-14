"""Application settings loaded from environment variables and config files.

Configuration is loaded from (highest priority first):
1. Environment variables (prefix: ``SPVWALLET_``, nested via ``__``)
2. YAML config file (``--config path`` or ``SPVWALLET_CONFIG_PATH`` env var)
3. Defaults defined here
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Enums for validated choices
# ---------------------------------------------------------------------------


class DatabaseEngine(enum.StrEnum):
    """Supported database engines."""

    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class CacheEngine(enum.StrEnum):
    """Supported cache backends."""

    MEMORY = "memory"
    REDIS = "redis"


class ArcWaitFor(enum.StrEnum):
    """ARC broadcast wait strategy."""

    SEEN_ON_NETWORK = "SEEN_ON_NETWORK"
    STORED = "STORED"
    ANNOUNCED_TO_NETWORK = "ANNOUNCED_TO_NETWORK"
    REQUESTED_BY_NETWORK = "REQUESTED_BY_NETWORK"
    SENT_TO_NETWORK = "SENT_TO_NETWORK"


# ---------------------------------------------------------------------------
# Sub-config models
# ---------------------------------------------------------------------------


class ServerConfig(BaseSettings):
    """HTTP server settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_SERVER__",
        case_sensitive=False,
    )

    host: str = "0.0.0.0"  # noqa: S104
    port: int = 3003
    idle_timeout: int = 60
    read_timeout: int = 40
    write_timeout: int = 40


class DatabaseConfig(BaseSettings):
    """Database settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_DB__",
        case_sensitive=False,
    )

    engine: DatabaseEngine = Field(
        default=DatabaseEngine.SQLITE,
        description="Database backend: sqlite or postgresql",
    )
    dsn: str = Field(
        default="sqlite+aiosqlite:///./spv_wallet.db",
        description="Async database connection string",
    )
    table_prefix: str = ""
    max_idle_connections: int = 5
    max_open_connections: int = 10
    debug_sql: bool = False


class CacheConfig(BaseSettings):
    """Cache settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_CACHE__",
        case_sensitive=False,
    )

    engine: CacheEngine = Field(
        default=CacheEngine.MEMORY,
        description="Cache backend: memory or redis",
    )
    url: str = "redis://localhost:6379/0"
    max_connections: int = 10
    ttl_seconds: int = 300


class ARCConfig(BaseSettings):
    """ARC transaction broadcaster settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_ARC__",
        case_sensitive=False,
    )

    url: str = "https://arc.taal.com"
    token: str = ""
    deployment_id: str = ""
    callback_url: str = ""
    callback_token: str = ""
    wait_for: ArcWaitFor = ArcWaitFor.SEEN_ON_NETWORK


class BHSConfig(BaseSettings):
    """Block Headers Service settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_BHS__",
        case_sensitive=False,
    )

    url: str = "https://bhs.taal.com"
    auth_token: str = ""


class PaymailConfig(BaseSettings):
    """Paymail settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_PAYMAIL__",
        case_sensitive=False,
    )

    domains: list[str] = Field(default_factory=list)
    sender_validation: bool = True
    default_from_paymail: str = ""
    beef_enabled: bool = True


class MetricsConfig(BaseSettings):
    """Prometheus metrics settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_METRICS__",
        case_sensitive=False,
    )

    enabled: bool = True
    port: int = 9090


class TaskConfig(BaseSettings):
    """Background task queue settings."""

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_TASK__",
        case_sensitive=False,
    )

    enabled: bool = True
    redis_url: str = "redis://localhost:6379/1"
    max_jobs: int = 100
    job_timeout: int = 300


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


def _load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML configuration file and return its contents as a dict.

    Returns an empty dict if the file doesn't exist or is empty.
    """
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


class AppConfig(BaseSettings):
    """Top-level application configuration.

    Loads settings from environment variables (``SPVWALLET_`` prefix),
    an optional YAML file, and built-in defaults.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPVWALLET_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    debug: bool = False
    version: str = "0.1.0"
    admin_xpub: str = ""
    encryption_key: str = ""
    config_path: str = ""

    server: ServerConfig = Field(default_factory=ServerConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    arc: ARCConfig = Field(default_factory=ARCConfig)
    bhs: BHSConfig = Field(default_factory=BHSConfig)
    paymail: PaymailConfig = Field(default_factory=PaymailConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    task: TaskConfig = Field(default_factory=TaskConfig)

    @model_validator(mode="before")
    @classmethod
    def _merge_yaml(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Merge YAML config file contents under the env var overrides."""
        config_path = values.get("config_path", "")
        if not config_path:
            return values
        yaml_data = _load_yaml(config_path)
        # YAML values serve as defaults; env vars (already in *values*) win.
        for key, val in yaml_data.items():
            if key not in values or values[key] is None:
                values[key] = val
            elif isinstance(val, dict) and isinstance(values.get(key), dict):
                # Merge nested dicts: YAML fills in missing keys
                merged = {**val, **values[key]}
                values[key] = merged
        return values

    @classmethod
    def from_yaml(cls, path: str | Path) -> Self:
        """Construct ``AppConfig`` loading defaults from a YAML file.

        Environment variables still override YAML values.
        """
        return cls(config_path=str(path))
