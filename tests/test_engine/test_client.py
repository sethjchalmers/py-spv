"""Tests for the SPVWalletEngine client."""

from __future__ import annotations

import pytest

from spv_wallet.engine.client import SPVWalletEngine


def test_engine_can_be_instantiated(app_config):
    """Engine should accept an AppConfig and construct without error."""
    engine = SPVWalletEngine(config=app_config)
    assert engine._config is app_config


@pytest.mark.asyncio
async def test_engine_initialise_and_close(app_config):
    """Engine initialise/close lifecycle should not raise."""
    engine = SPVWalletEngine(config=app_config)
    await engine.initialise()
    await engine.close()
