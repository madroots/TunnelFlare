from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtCore import Qt
import qrcode


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


class QRCodeDialog(QDialog):
    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QR Code")
        self.setFixedSize(300, 350)
        self.url = url
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)

        pixmap = QPixmap.fromImage(render_qr_image(self.url))

        # Display
        qr_label = QLabel()
        qr_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        qr_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(qr_label)

        # Helper text
        layout.addWidget(QLabel("Scan to open on mobile"))
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
