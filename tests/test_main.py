"""Tests for spv_wallet.main entry point."""

from __future__ import annotations

from unittest.mock import patch


def test_main_calls_uvicorn_run() -> None:
    """Verify that main() delegates to uvicorn.run with expected args."""
    with patch("spv_wallet.main.uvicorn.run") as mock_run:
        from spv_wallet.main import main

        main()
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        assert call_kwargs[0][0] == "spv_wallet.api.app:create_app"
        assert call_kwargs[1]["factory"] is True
        assert call_kwargs[1]["port"] == 3003
