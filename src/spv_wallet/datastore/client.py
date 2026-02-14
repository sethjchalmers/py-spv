"""Datastore client — async SQLAlchemy engine & session management.

Central datastore abstraction providing:
- Engine lifecycle (create, dispose)
- Async session factory
- Table creation / migration support
- Table prefix support via naming conventions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from spv_wallet.datastore.engines import create_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.orm import DeclarativeBase

    from spv_wallet.config.settings import DatabaseConfig


class Datastore:
    """Async datastore wrapping a SQLAlchemy engine and session factory.

    Usage::

        ds = Datastore(db_config)
        await ds.open()
        async with ds.session() as session:
            ...
        await ds.close()
    """

    def __init__(self, config: DatabaseConfig) -> None:
        self._config = config
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Return the underlying async engine.

        Raises:
            RuntimeError: If the datastore is not open.
        """
        if self._engine is None:
            msg = "Datastore is not open. Call open() first."
            raise RuntimeError(msg)
        return self._engine

    async def open(self, *, base: type[DeclarativeBase] | None = None) -> None:
        """Open the datastore — create engine and optionally create tables.

        Args:
            base: If provided, create all tables defined by this declarative base.
                  Primarily used for SQLite in-memory testing.
        """
        self._engine = create_engine(self._config)
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        if base is not None:
            async with self._engine.begin() as conn:
                await conn.run_sync(base.metadata.create_all)

    async def close(self) -> None:
        """Dispose the engine and release all connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def session(self) -> AsyncSession:
        """Create a new async session from the session factory.

        Returns:
            An ``AsyncSession`` instance. Use as an async context manager.

        Raises:
            RuntimeError: If the datastore is not open.
        """
        if self._session_factory is None:
            msg = "Datastore is not open. Call open() first."
            raise RuntimeError(msg)
        return self._session_factory()

    async def session_iterator(self) -> AsyncIterator[AsyncSession]:
        """FastAPI-style dependency yielding a session.

        Yields:
            An ``AsyncSession`` that is committed on success and rolled back on error.
        """
        session = self.session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @property
    def table_prefix(self) -> str:
        """Return the configured table prefix."""
        return self._config.table_prefix

    @property
    def is_open(self) -> bool:
        """Check if the datastore is open."""
        return self._engine is not None
