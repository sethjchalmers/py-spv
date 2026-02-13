"""Database engine factories — PostgreSQL, SQLite.

Provides async SQLAlchemy engine creation with support for:
- PostgreSQL (asyncpg driver)
- SQLite (aiosqlite driver)
- Configurable pool sizes and echo/debug settings
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

if TYPE_CHECKING:
    from spv_wallet.config.settings import DatabaseConfig


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    """Create an async SQLAlchemy engine from database configuration.

    Args:
        config: Database configuration with DSN, pool settings, etc.

    Returns:
        A configured ``AsyncEngine`` ready for use.
    """
    kwargs: dict = {
        "echo": config.debug_sql,
    }

    # SQLite doesn't support pool settings in the same way
    if "sqlite" not in config.dsn:
        kwargs["pool_size"] = config.max_idle_connections
        kwargs["max_overflow"] = config.max_open_connections - config.max_idle_connections
        kwargs["pool_pre_ping"] = True

    return create_async_engine(config.dsn, **kwargs)
