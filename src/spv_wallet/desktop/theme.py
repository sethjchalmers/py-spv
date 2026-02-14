"""Desktop theme — VSCode dark palette with BSV gold accents.

Design principles:
  • Dark background (#1e1e1e base) with soft greys for layering
  • BSV gold (#eab308) for primary actions, highlights, and accents
  • High-contrast text (#e4e4e4 on dark) for readability
  • Large click targets and clear spacing for non-technical users
  • All dimensions in logical pixels — portable to mobile via scaling
  • QSS stylesheet exported as a single string for QApplication.setStyleSheet()
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Palette:
    """Named colour tokens — single source of truth."""

    # Backgrounds (VSCode layering)
    bg_base: str = "#1e1e1e"  # editor background
    bg_surface: str = "#252526"  # side-bar / panels
    bg_elevated: str = "#2d2d2d"  # cards, dialogs
    bg_input: str = "#3c3c3c"  # text inputs, dropdowns
    bg_hover: str = "#2a2d2e"  # list-item / button hover
    bg_selected: str = "#37373d"  # selected row / tab

    # Borders
    border: str = "#3e3e42"  # subtle separator
    border_focus: str = "#eab308"  # focused input ring (BSV gold)

    # Text
    text_primary: str = "#e4e4e4"  # body text
    text_secondary: str = "#969696"  # labels, hints
    text_muted: str = "#6a6a6a"  # disabled, placeholder
    text_inverse: str = "#1e1e1e"  # text on accent buttons

    # BSV accent (yellow / gold)
    accent: str = "#eab308"  # primary action
    accent_hover: str = "#facc15"  # button hover
    accent_pressed: str = "#ca8a04"  # button pressed
    accent_muted: str = "#854d0e"  # subtle badge / tag

    # Semantic
    success: str = "#22c55e"  # confirmed, synced
    warning: str = "#f59e0b"  # pending, unconfirmed
    error: str = "#ef4444"  # failed, invalid
    info: str = "#3b82f6"  # informational

    # Scrollbar
    scrollbar_bg: str = "#1e1e1e"
    scrollbar_handle: str = "#424242"
    scrollbar_hover: str = "#555555"


# Singleton palette
PALETTE = Palette()

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

# Font stack — system fonts first (renders natively on every OS + mobile),
# then fallback to monospace for addresses / hashes.
FONT_FAMILY = '".AppleSystemUIFont", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
FONT_MONO = '"SF Mono", "Cascadia Code", "Fira Code", Consolas, monospace'

FONT_SIZE_XS = 11  # captions, timestamps
FONT_SIZE_SM = 13  # secondary labels
FONT_SIZE_MD = 14  # body text (default)
FONT_SIZE_LG = 16  # sub-headings
FONT_SIZE_XL = 20  # panel titles
FONT_SIZE_XXL = 28  # hero balance display

# ---------------------------------------------------------------------------
# Spacing & sizing
# ---------------------------------------------------------------------------

SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_XXL = 32

RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8

BUTTON_HEIGHT = 36
BUTTON_HEIGHT_LG = 44
INPUT_HEIGHT = 36

# ---------------------------------------------------------------------------
# QSS stylesheet
# ---------------------------------------------------------------------------


def build_stylesheet(p: Palette | None = None) -> str:
    """Generate a complete Qt Style Sheet for the application.

    Args:
        p: Palette to use. Defaults to the built-in dark theme.

    Returns:
        QSS string suitable for ``QApplication.setStyleSheet()``.
    """
    if p is None:
        p = PALETTE

    return f"""
    /* ===== Global ===== */
    * {{
        color: {p.text_primary};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE_MD}px;
        outline: none;
    }}

    QMainWindow, QDialog, QWidget {{
        background-color: {p.bg_base};
    }}

    /* ===== Scroll areas ===== */
    QScrollArea {{
        border: none;
        background-color: {p.bg_base};
    }}
    QScrollBar:vertical {{
        background: {p.scrollbar_bg};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {p.scrollbar_handle};
        min-height: 30px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p.scrollbar_hover};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {p.scrollbar_bg};
        height: 10px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p.scrollbar_handle};
        min-width: 30px;
        border-radius: 5px;
    }}

    /* ===== Labels ===== */
    QLabel {{
        background: transparent;
        padding: 0;
    }}
    QLabel[role="heading"] {{
        font-size: {FONT_SIZE_XL}px;
        font-weight: 600;
        color: {p.text_primary};
    }}
    QLabel[role="subheading"] {{
        font-size: {FONT_SIZE_LG}px;
        font-weight: 500;
        color: {p.text_secondary};
    }}
    QLabel[role="caption"] {{
        font-size: {FONT_SIZE_XS}px;
        color: {p.text_muted};
    }}
    QLabel[role="balance"] {{
        font-size: {FONT_SIZE_XXL}px;
        font-weight: 700;
        color: {p.accent};
    }}
    QLabel[role="mono"] {{
        font-family: {FONT_MONO};
        font-size: {FONT_SIZE_SM}px;
        color: {p.text_secondary};
    }}

    /* ===== Buttons ===== */
    QPushButton {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        padding: {SPACING_SM}px {SPACING_LG}px;
        min-height: {BUTTON_HEIGHT}px;
        font-weight: 500;
    }}
    QPushButton:hover {{
        background-color: {p.bg_hover};
        border-color: {p.accent};
    }}
    QPushButton:pressed {{
        background-color: {p.bg_selected};
    }}
    QPushButton:disabled {{
        color: {p.text_muted};
        border-color: {p.border};
        background-color: {p.bg_surface};
    }}
    QPushButton[role="primary"] {{
        background-color: {p.accent};
        color: {p.text_inverse};
        border: none;
        font-weight: 600;
    }}
    QPushButton[role="primary"]:hover {{
        background-color: {p.accent_hover};
    }}
    QPushButton[role="primary"]:pressed {{
        background-color: {p.accent_pressed};
    }}
    QPushButton[role="primary"]:disabled {{
        background-color: {p.accent_muted};
        color: {p.text_muted};
    }}
    QPushButton[role="danger"] {{
        background-color: {p.error};
        color: {p.text_primary};
        border: none;
    }}
    QPushButton[role="nav"] {{
        background-color: transparent;
        border: none;
        border-radius: {RADIUS_SM}px;
        text-align: left;
        padding: {SPACING_MD}px {SPACING_LG}px;
        min-height: {BUTTON_HEIGHT_LG}px;
        font-size: {FONT_SIZE_MD}px;
        color: {p.text_secondary};
    }}
    QPushButton[role="nav"]:hover {{
        background-color: {p.bg_hover};
        color: {p.text_primary};
    }}
    QPushButton[role="nav"]:checked {{
        background-color: {p.bg_selected};
        color: {p.accent};
        font-weight: 600;
    }}

    /* ===== Text inputs ===== */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        padding: {SPACING_SM}px {SPACING_MD}px;
        min-height: {INPUT_HEIGHT}px;
        selection-background-color: {p.accent_muted};
        selection-color: {p.text_primary};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {p.accent};
    }}
    QLineEdit:disabled {{
        color: {p.text_muted};
        background-color: {p.bg_surface};
    }}
    QLineEdit[role="mono"] {{
        font-family: {FONT_MONO};
        font-size: {FONT_SIZE_SM}px;
    }}

    /* ===== Combo / Dropdown ===== */
    QComboBox {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        padding: {SPACING_SM}px {SPACING_MD}px;
        min-height: {INPUT_HEIGHT}px;
    }}
    QComboBox:hover {{
        border-color: {p.accent};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border: 1px solid {p.border};
        selection-background-color: {p.bg_selected};
    }}

    /* ===== Spin box ===== */
    QSpinBox, QDoubleSpinBox {{
        background-color: {p.bg_input};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        padding: {SPACING_SM}px;
        min-height: {INPUT_HEIGHT}px;
    }}

    /* ===== Tables ===== */
    QTableWidget, QTableView {{
        background-color: {p.bg_surface};
        alternate-background-color: {p.bg_elevated};
        gridline-color: {p.border};
        border: none;
        selection-background-color: {p.bg_selected};
        selection-color: {p.text_primary};
    }}
    QHeaderView::section {{
        background-color: {p.bg_elevated};
        color: {p.text_secondary};
        font-weight: 600;
        font-size: {FONT_SIZE_SM}px;
        border: none;
        border-bottom: 1px solid {p.border};
        padding: {SPACING_SM}px {SPACING_MD}px;
        min-height: {BUTTON_HEIGHT}px;
    }}

    /* ===== Tab widget (fallback) ===== */
    QTabWidget::pane {{
        border: 1px solid {p.border};
        border-radius: {RADIUS_MD}px;
        background-color: {p.bg_base};
    }}
    QTabBar::tab {{
        background-color: {p.bg_surface};
        color: {p.text_secondary};
        padding: {SPACING_SM}px {SPACING_LG}px;
        border: none;
        border-bottom: 2px solid transparent;
        min-width: 80px;
    }}
    QTabBar::tab:selected {{
        color: {p.text_primary};
        border-bottom-color: {p.accent};
    }}
    QTabBar::tab:hover {{
        color: {p.text_primary};
        background-color: {p.bg_hover};
    }}

    /* ===== Group box ===== */
    QGroupBox {{
        background-color: {p.bg_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS_LG}px;
        margin-top: {SPACING_LG}px;
        padding: {SPACING_XL}px {SPACING_LG}px {SPACING_LG}px {SPACING_LG}px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 {SPACING_SM}px;
        color: {p.text_secondary};
    }}

    /* ===== Progress bar ===== */
    QProgressBar {{
        background-color: {p.bg_input};
        border: none;
        border-radius: {RADIUS_SM}px;
        min-height: 8px;
        max-height: 8px;
        text-align: center;
        font-size: 0px;
    }}
    QProgressBar::chunk {{
        background-color: {p.accent};
        border-radius: {RADIUS_SM}px;
    }}

    /* ===== Tooltips ===== */
    QToolTip {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border: 1px solid {p.border};
        border-radius: {RADIUS_SM}px;
        padding: {SPACING_SM}px;
        font-size: {FONT_SIZE_SM}px;
    }}

    /* ===== Status bar ===== */
    QStatusBar {{
        background-color: {p.bg_surface};
        color: {p.text_secondary};
        font-size: {FONT_SIZE_XS}px;
        border-top: 1px solid {p.border};
    }}
    QStatusBar QLabel {{
        padding: 0 {SPACING_SM}px;
    }}

    /* ===== Wizard ===== */
    QWizard {{
        background-color: {p.bg_base};
    }}
    QWizardPage {{
        background-color: {p.bg_base};
    }}

    /* ===== Checkbox / Radio ===== */
    QCheckBox, QRadioButton {{
        spacing: {SPACING_SM}px;
        color: {p.text_primary};
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 18px;
        height: 18px;
    }}

    /* ===== Frame / separator ===== */
    QFrame[role="separator"] {{
        background-color: {p.border};
        max-height: 1px;
        min-height: 1px;
    }}

    /* ===== Card container ===== */
    QFrame[role="card"] {{
        background-color: {p.bg_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS_LG}px;
        padding: {SPACING_LG}px;
    }}

    /* ===== Menu ===== */
    QMenuBar {{
        background-color: {p.bg_surface};
        color: {p.text_primary};
        border-bottom: 1px solid {p.border};
    }}
    QMenuBar::item:selected {{
        background-color: {p.bg_hover};
    }}
    QMenu {{
        background-color: {p.bg_elevated};
        color: {p.text_primary};
        border: 1px solid {p.border};
    }}
    QMenu::item:selected {{
        background-color: {p.bg_selected};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {p.border};
        margin: {SPACING_SM}px {SPACING_MD}px;
    }}
    """


# Pre-built stylesheet (import and use directly)
DARK_STYLESHEET = build_stylesheet()
