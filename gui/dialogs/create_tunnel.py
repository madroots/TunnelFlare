from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt
from ..styles import Styles

class CreateTunnelDialog(QDialog):
    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Add Tunnel")
        self.setFixedWidth(350)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 28, 24, 32)
        
        layout.addWidget(QLabel("Tunnel Name", objectName="PortLabel"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. backend-api")
        layout.addWidget(self.name_input)

        layout.addSpacing(12)
        layout.addWidget(QLabel("🔌 Local Port", objectName="PortLabel"))
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("3000")
        layout.addWidget(self.port_input)

        layout.addSpacing(24)
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(48)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        
        self.save_btn = QPushButton("Add Tunnel")
        self.save_btn.setObjectName("PrimaryAction")
        self.save_btn.setMinimumHeight(48)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.validate_and_accept)
        
        btn_layout.addWidget(self.cancel_btn, 1)
        btn_layout.addWidget(self.save_btn, 1)
        layout.addLayout(btn_layout)

    def validate_and_accept(self):
        name = self.name_input.text().strip()
        port_text = self.port_input.text()
        
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a name.")
            return

        if not port_text.isdigit() or not (1 <= int(port_text) <= 65535):
            QMessageBox.warning(self, "Invalid Port", "Please enter a valid port number.")
            return
        
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "port": int(self.port_input.text())
        }
