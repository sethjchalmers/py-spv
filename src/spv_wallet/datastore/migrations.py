"""Auto-migration support via Alembic.

Provides programmatic migration execution for the SPV wallet engine,
matching the Go ``AutoMigrate`` behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spv_wallet.engine.models.base import Base

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine


async def run_auto_migrate(engine: AsyncEngine) -> None:
    """Create all tables defined by ORM models (development/testing convenience).

    For production, use Alembic migration scripts instead.

    Args:
        engine: The async SQLAlchemy engine to migrate.
    """
    # Import all models to register them with Base.metadata
    import spv_wallet.engine.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables(engine: AsyncEngine) -> None:
    """Drop all tables (test/dev utility only — never use in production!).

    Args:
        engine: The async SQLAlchemy engine.
    """
    import spv_wallet.engine.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
