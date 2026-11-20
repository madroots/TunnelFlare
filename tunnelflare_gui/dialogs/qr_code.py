import qrcode
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..components.elided_label import ElidedLabel

QR_SIZE = 200  # px, upper bound for the code inside its white tile


def render_qr_image(data, box_size=10, border=2):
    """Paint the QR code for ``data`` as black modules on white, ``box_size`` px each."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()  # includes the quiet-zone border

    size = len(matrix) * box_size
    image = QImage(size, size, QImage.Format_RGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                painter.fillRect(x * box_size, y * box_size, box_size, box_size, Qt.black)
    painter.end()
    return image


def crisp_qr_pixmap(data, max_size, device_pixel_ratio):
    """The QR code at a whole number of device pixels per module, so it never blurs."""
    modules = render_qr_image(data, box_size=1, border=0).width()
    box = max(1, int(max_size * device_pixel_ratio) // modules)
    pixmap = QPixmap.fromImage(render_qr_image(data, box_size=box, border=0))
    pixmap.setDevicePixelRatio(device_pixel_ratio)
    return pixmap


class QRCodeDialog(QDialog):
    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TunnelFlare")
        self.setFixedWidth(360)
        self.url = url
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 24)
        layout.setSpacing(0)

        title = QLabel("Scan to open on your phone")
        title.setObjectName("DialogTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(6)
        text = QLabel("Point your phone’s camera at the code.")
        text.setObjectName("DialogText")
        text.setAlignment(Qt.AlignCenter)
        layout.addWidget(text)
        layout.addSpacing(20)

        tile = QFrame()
        tile.setObjectName("QrTile")
        tile.setFixedSize(QR_SIZE + 36, QR_SIZE + 36)
        tile_layout = QVBoxLayout(tile)
        tile_layout.setContentsMargins(0, 0, 0, 0)
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setPixmap(crisp_qr_pixmap(self.url, QR_SIZE, self.devicePixelRatioF()))
        self.qr_label.setAccessibleName(f"QR code for {self.url}")
        tile_layout.addWidget(self.qr_label)
        layout.addWidget(tile, 0, Qt.AlignHCenter)
        layout.addSpacing(14)

        caption = ElidedLabel(self.url.removeprefix("https://"))
        caption.setObjectName("QrCaption")
        caption.setAlignment(Qt.AlignCenter)
        caption.setToolTip(self.url)
        layout.addWidget(caption)
        layout.addSpacing(22)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.copy_btn = QPushButton("Copy Link")
        self.copy_btn.setMinimumHeight(44)
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setAutoDefault(False)
        self.copy_btn.clicked.connect(self.copy_link)
        done = QPushButton("Done")
        done.setObjectName("PrimaryAction")
        done.setMinimumHeight(44)
        done.setCursor(Qt.PointingHandCursor)
        done.setDefault(True)
        done.clicked.connect(self.accept)
        buttons.addWidget(self.copy_btn, 1)
        buttons.addWidget(done, 1)
        layout.addLayout(buttons)

    def copy_link(self):
        QApplication.clipboard().setText(self.url)
        self.copy_btn.setText("Copied")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy Link"))
