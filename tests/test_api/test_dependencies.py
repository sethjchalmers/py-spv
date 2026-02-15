"""Tests for FastAPI dependency injection helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request

from spv_wallet.api.dependencies import get_engine
from spv_wallet.errors.spv_errors import SPVError


class TestGetEngine:
    def test_returns_engine_from_state(self):
        app = FastAPI()
        engine = MagicMock()
        app.state.engine = engine

        request = MagicMock(spec=Request)
        request.app = app

        result = get_engine(request)
        assert result is engine

    def test_raises_if_no_engine(self):
        app = FastAPI()
        # No engine set on state

        request = MagicMock(spec=Request)
        request.app = app

        with pytest.raises(SPVError, match="unauthorized"):
            get_engine(request)
