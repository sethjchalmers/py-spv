"""Shared test fixtures for py-spv test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from spv_wallet.config.settings import DatabaseEngine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@pytest.fixture
def app_config():
    """Provide a test AppConfig with safe defaults."""
    from spv_wallet.config.settings import AppConfig, DatabaseConfig

    return AppConfig(
        debug=True,
        admin_xpub="xpub_test_admin",
        encryption_key="test-encryption-key-32bytes!!!!!",
        db=DatabaseConfig(
            engine=DatabaseEngine.SQLITE,
            dsn="sqlite+aiosqlite:///:memory:",
        ),
    )


@pytest.fixture
async def async_engine(app_config):
    """Create an async SQLAlchemy engine for testing (in-memory SQLite)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(app_config.db.dsn, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncIterator:
    """Provide a scoped async database session for a test."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    async_session = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
def test_client(app_config):
    """Provide a FastAPI TestClient with the app wired to test config."""
    from fastapi.testclient import TestClient

    from spv_wallet.api.app import create_app

    app = create_app(config=app_config)
    return TestClient(app, raise_server_exceptions=False)
