"""Common reusable widgets — cards, separators, helpers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


# ---------------------------------------------------------------------------
# Typed labels (with QSS role property)
# ---------------------------------------------------------------------------


def heading_label(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Create a heading-styled ``QLabel`` (role='heading')."""
    lbl = QLabel(text, parent)
    lbl.setProperty("role", "heading")
    return lbl


def subheading_label(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Create a sub-heading-styled ``QLabel`` (role='subheading')."""
    lbl = QLabel(text, parent)
    lbl.setProperty("role", "subheading")
    return lbl


def caption_label(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Create a caption-styled ``QLabel`` (role='caption')."""
    lbl = QLabel(text, parent)
    lbl.setProperty("role", "caption")
    return lbl


def balance_label(text: str = "0", parent: QWidget | None = None) -> QLabel:
    """Create a balance-styled ``QLabel`` (role='balance')."""
    lbl = QLabel(text, parent)
    lbl.setProperty("role", "balance")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


def mono_label(text: str = "", parent: QWidget | None = None) -> QLabel:
    """Create a monospace ``QLabel`` (role='mono') for addresses & hashes."""
    lbl = QLabel(text, parent)
    lbl.setProperty("role", "mono")
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lbl


# ---------------------------------------------------------------------------
# Structural widgets
# ---------------------------------------------------------------------------


class Separator(QFrame):
    """Thin horizontal separator line (role='separator')."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "separator")
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)


class Card(QFrame):
    """A card container with rounded corners (role='card').

    Usage::

        card = Card()
        card.layout().addWidget(my_content)
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(8)

    def layout(self) -> QVBoxLayout:
        return self._layout


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def hbox(*widgets: QWidget, spacing: int = 8) -> QHBoxLayout:
    """Build an ``QHBoxLayout`` with the given widgets."""
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        layout.addWidget(w)
    return layout


def vbox(*widgets: QWidget, spacing: int = 8) -> QVBoxLayout:
    """Build a ``QVBoxLayout`` with the given widgets."""
    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        layout.addWidget(w)
    return layout
