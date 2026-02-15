"""Desktop application entry point — QApplication lifecycle.

Launch flow:
  1. Apply dark theme stylesheet
  2. Show WalletWizard (file + xPub import)
  3. Initialize engine with chosen wallet path
  4. Register xPub
  5. Show MainWindow
"""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the py-spv desktop application."""
    try:
        from PySide6.QtWidgets import QApplication, QWizard

        from spv_wallet.desktop.main_window import MainWindow
        from spv_wallet.desktop.theme import DARK_STYLESHEET
        from spv_wallet.desktop.wallet_api import WalletAPI
        from spv_wallet.desktop.wallet_wizard import WalletWizard
    except ImportError:
        print(  # noqa: T201
            "Desktop dependencies not installed. Install with: pip install py-spv[desktop]"
        )
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("py-spv")
    app.setOrganizationName("py-spv")

    # Apply global dark theme
    app.setStyleSheet(DARK_STYLESHEET)

    # Run wallet setup wizard
    wizard = WalletWizard()
    if wizard.exec() != QWizard.DialogCode.Accepted:
        sys.exit(0)

    wallet_path = wizard.wallet_path()
    raw_xpub = wizard.raw_xpub()

    # Create API bridge & main window
    api = WalletAPI()
    window = MainWindow(api=api)
    window.show()

    # Initialize engine (async, non-blocking)
    if raw_xpub:
        api.engine_ready.connect(lambda: api.register_xpub(raw_xpub))
    api.initialize(wallet_path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
