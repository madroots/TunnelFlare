from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from tunnelflare_backend.config_manager import tunnel_id_for
from ..resources import RESOURCE_DIR


class TunnelDialog(QDialog):
    """Add a tunnel, or edit an existing one when `tunnel` (its saved config) is given."""

    def __init__(self, parent=None, config_manager=None, tunnel=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.original_name = tunnel['name'] if tunnel else None
        self.setWindowTitle("Edit Tunnel" if tunnel else "Add Tunnel")
        self.setFixedWidth(380)
        self.setup_ui()
        if tunnel:
            self.name_input.setText(tunnel['name'])
            self.port_input.setText(str(tunnel['port']))
            self.https_check.setChecked(tunnel.get('protocol') == 'https')
            self.rewrite_check.setChecked(bool(tunnel.get('rewrite_host')))

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 28, 24, 32)
        
        layout.addWidget(QLabel("Tunnel Name", objectName="PortLabel"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. backend-api")
        layout.addWidget(self.name_input)

        layout.addSpacing(12)
        port_header_layout = QHBoxLayout()
        port_header_layout.setSpacing(6)
        
        port_icon = QLabel()
        port_icon.setPixmap(QIcon(str(RESOURCE_DIR / "port.svg")).pixmap(16, 16))
        
        port_label = QLabel("Local Port")
        port_label.setObjectName("PortLabel")
        
        port_header_layout.addWidget(port_icon)
        port_header_layout.addWidget(port_label)
        port_header_layout.addStretch()
        layout.addLayout(port_header_layout)

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("3000")
        layout.addWidget(self.port_input)

        layout.addSpacing(8)
        self.https_check = QCheckBox("My local server uses HTTPS")
        layout.addWidget(self.https_check)
        layout.addWidget(self._hint("Self-signed certificates are accepted."))

        self.rewrite_check = QCheckBox("Send requests as “localhost”")
        layout.addWidget(self.rewrite_check)
        layout.addWidget(self._hint(
            "Rewrites the Host header. Fixes “Invalid Host header” and “Blocked request” "
            "errors from Vite, webpack and Django dev servers."
        ))

        layout.addSpacing(16)
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(48)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("Save" if self.original_name else "Add Tunnel")
        self.save_btn.setObjectName("PrimaryAction")
        self.save_btn.setMinimumHeight(48)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.validate_and_accept)
        
        btn_layout.addWidget(self.cancel_btn, 1)
        btn_layout.addWidget(self.save_btn, 1)
        layout.addLayout(btn_layout)

    @staticmethod
    def _hint(text):
        hint = QLabel(text)
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        hint.setContentsMargins(28, 0, 0, 4)
        return hint

    def validate_and_accept(self):
        name = self.name_input.text().strip()
        port_text = self.port_input.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a name.")
            return

        conflict = self.config_manager.name_conflict(name, ignore=self.original_name)
        if conflict:
            if conflict == name:
                message = f"A tunnel named “{name}” already exists. Please choose another name."
            else:
                message = (f"“{name}” is too similar to the existing tunnel “{conflict}”: both would use "
                           f"the same log files ({tunnel_id_for(name)}). Please choose another name.")
            QMessageBox.warning(self, "Name Already Used", message)
            return

        if not port_text.isdigit() or not (1 <= int(port_text) <= 65535):
            QMessageBox.warning(self, "Invalid Port", "Please enter a valid port number.")
            return
        
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "port": int(self.port_input.text().strip()),
            "protocol": "https" if self.https_check.isChecked() else "http",
            "rewrite_host": self.rewrite_check.isChecked(),
        }
