"""QR code renderer widget — displays BSV addresses / payment URIs as QR."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class QRWidget(QLabel):
    """A ``QLabel`` that renders a QR code from arbitrary text.

    Falls back to a placeholder message when ``qrcode`` is not installed.
    """

    def __init__(self, parent: QWidget | None = None, size: int = 200) -> None:
        super().__init__(parent)
        self._size = size
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setText("No QR data")
        self.setProperty("role", "mono")

    def set_data(self, data: str) -> None:
        """Render a QR code for *data* (address or URI).

        If the ``qrcode`` library is unavailable, shows the raw text instead.
        """
        if not data:
            self.setPixmap(QPixmap())
            self.setText("No QR data")
            return
        try:
            import qrcode  # noqa: PLC0415
            from qrcode.image.pil import PilImage  # noqa: PLC0415

            img = qrcode.make(data, image_factory=PilImage, box_size=8, border=2)
            # Convert PIL → QImage → QPixmap
            pil_img = img.get_image().convert("RGBA")
            raw = pil_img.tobytes("raw", "RGBA")
            qimg = QImage(
                raw, pil_img.width, pil_img.height, QImage.Format.Format_RGBA8888,
            )
            pixmap = QPixmap.fromImage(qimg).scaled(
                self._size, self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(pixmap)
            self.setText("")
        except ImportError:
            self.setText(data)
