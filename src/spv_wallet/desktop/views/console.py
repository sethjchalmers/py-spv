"""Interactive Python console tab — embedded REPL with wallet context."""

from __future__ import annotations

import io
import sys
import traceback
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from spv_wallet.desktop.widgets.common import caption_label, heading_label

if TYPE_CHECKING:
    from spv_wallet.desktop.wallet_api import WalletAPI

_BANNER = "py-spv Console\nType Python expressions. `api` is the WalletAPI instance.\n>>> "


class ConsolePanel(QWidget):
    """Embedded interactive Python console with wallet context.

    Provides a simple REPL where ``api`` is bound to the
    ``WalletAPI`` instance for quick inspection and scripting.
    """

    def __init__(self, api: WalletAPI, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._history: list[str] = []
        self._history_idx = 0
        self._namespace: dict[str, Any] = {"api": api}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        layout.addWidget(heading_label("Console"))
        layout.addWidget(
            caption_label("Interactive Python environment"),
        )

        self._output = _ConsoleEdit(self._on_input)
        font = QFont("Menlo, Consolas, monospace", 12)
        self._output.setFont(font)
        self._output.setStyleSheet("background-color: #1a1a1a; color: #d4d4d4; padding: 8px;")
        self._output.append(_BANNER)
        layout.addWidget(self._output, stretch=1)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _on_input(self, line: str) -> None:
        """Execute a line of Python."""
        line = line.strip()
        if line:
            self._history.append(line)
            self._history_idx = len(self._history)

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            try:
                result = eval(line, self._namespace)  # noqa: S307
                if result is not None:
                    print(repr(result))  # noqa: T201
            except SyntaxError:
                exec(line, self._namespace)  # noqa: S102
        except Exception:
            traceback.print_exc(file=stdout_capture)
        finally:
            sys.stdout = old_stdout

        output = stdout_capture.getvalue()
        if output:
            self._output.append(output.rstrip())
        self._output.append(">>> ")
        self._output.moveCursor(QTextCursor.MoveOperation.End)

    def history_up(self) -> str:
        """Navigate history backwards."""
        if self._history and self._history_idx > 0:
            self._history_idx -= 1
            return self._history[self._history_idx]
        return ""

    def history_down(self) -> str:
        """Navigate history forwards."""
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            return self._history[self._history_idx]
        self._history_idx = len(self._history)
        return ""


class _ConsoleEdit(QTextEdit):
    """QTextEdit that captures Return key for REPL input."""

    def __init__(
        self,
        on_input: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_input = on_input

    def keyPressEvent(  # type: ignore[override]
        self, event: QKeyEvent
    ) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.movePosition(
                QTextCursor.MoveOperation.StartOfLine,
                QTextCursor.MoveMode.KeepAnchor,
            )
            line = cursor.selectedText()
            if line.startswith(">>> "):
                line = line[4:]
            self.append("")
            self._on_input(line)
            return
        super().keyPressEvent(event)
