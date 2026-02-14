"""Desktop application tests — WalletAPI logic, widget helpers, theme.

These tests do NOT require a running QApplication or PySide6 display.
They test the non-GUI logic and data formatting.
"""

from __future__ import annotations

import pytest

# ============================================================================
# Theme tests (no Qt dependency)
# ============================================================================


class TestTheme:
    """Tests for the desktop theme system."""

    def test_palette_has_required_colours(self) -> None:
        from spv_wallet.desktop.theme import PALETTE

        assert PALETTE.bg_base == "#1e1e1e"
        assert PALETTE.accent == "#eab308"
        assert PALETTE.text_primary == "#e4e4e4"
        assert PALETTE.error == "#ef4444"
        assert PALETTE.success == "#22c55e"

    def test_build_stylesheet_returns_string(self) -> None:
        from spv_wallet.desktop.theme import build_stylesheet

        qss = build_stylesheet()
        assert isinstance(qss, str)
        assert "QMainWindow" in qss
        assert "#1e1e1e" in qss  # bg_base
        assert "#eab308" in qss  # accent

    def test_build_stylesheet_with_custom_palette(self) -> None:
        from spv_wallet.desktop.theme import Palette, build_stylesheet

        custom = Palette(accent="#ff0000")
        qss = build_stylesheet(custom)
        assert "#ff0000" in qss
        assert "#eab308" not in qss  # default accent not present

    def test_dark_stylesheet_singleton(self) -> None:
        from spv_wallet.desktop.theme import DARK_STYLESHEET, build_stylesheet

        assert build_stylesheet() == DARK_STYLESHEET

    def test_palette_is_frozen(self) -> None:
        from spv_wallet.desktop.theme import PALETTE

        with pytest.raises(AttributeError):
            PALETTE.accent = "#ff0000"  # type: ignore[misc]

    def test_stylesheet_covers_key_widgets(self) -> None:
        from spv_wallet.desktop.theme import DARK_STYLESHEET

        for widget in (
            "QPushButton",
            "QLineEdit",
            "QTableWidget",
            "QComboBox",
            "QTabBar",
            "QScrollBar",
            "QStatusBar",
            "QToolTip",
            "QWizard",
            "QProgressBar",
            "QMenuBar",
        ):
            assert widget in DARK_STYLESHEET, f"{widget} not styled"


# ============================================================================
# AmountEdit formatting helpers (no Qt dependency needed)
# ============================================================================


class TestAmountFormatting:
    """Test amount formatting static methods."""

    @pytest.mark.desktop
    def test_format_sats(self) -> None:
        from spv_wallet.desktop.widgets.amount_edit import AmountEdit

        assert AmountEdit.format_sats(0) == "0"
        assert AmountEdit.format_sats(1_000) == "1,000"
        assert AmountEdit.format_sats(100_000_000) == "100,000,000"

    @pytest.mark.desktop
    def test_format_bsv(self) -> None:
        from spv_wallet.desktop.widgets.amount_edit import AmountEdit

        assert AmountEdit.format_bsv(100_000_000) == "1.00000000 BSV"
        assert AmountEdit.format_bsv(1) == "0.00000001 BSV"
        assert AmountEdit.format_bsv(0) == "0.00000000 BSV"


# ============================================================================
# WalletAPI (AsyncWorker logic — can test without display)
# ============================================================================


@pytest.mark.desktop
class TestAsyncWorker:
    """Test AsyncWorker runs coroutines correctly."""

    def test_worker_signals_exist(self) -> None:
        from spv_wallet.desktop.wallet_api import _WorkerSignals

        signals = _WorkerSignals()
        assert hasattr(signals, "finished")
        assert hasattr(signals, "error")
