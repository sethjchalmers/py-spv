"""Desktop application entry point — QApplication lifecycle."""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the py-spv desktop application."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415

        from spv_wallet.desktop.main_window import MainWindow  # noqa: PLC0415
    except ImportError:
        print(  # noqa: T201
            "Desktop dependencies not installed. "
            "Install with: pip install py-spv[desktop]"
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("py-spv")
    app.setOrganizationName("py-spv")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
