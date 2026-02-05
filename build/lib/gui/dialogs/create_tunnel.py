from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt

class CreateTunnelDialog(QDialog):
    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Start New Tunnel")
        self.setFixedWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Name
        layout.addWidget(QLabel("Tunnel Name (Optional)"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. my-app")
        layout.addWidget(self.name_input)

        # Protocol
        layout.addWidget(QLabel("Protocol"))
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(["http", "https"])
        default_proto = self.config_manager.get("default_protocol", "http") if self.config_manager else "http"
        self.protocol_combo.setCurrentText(default_proto)
        layout.addWidget(self.protocol_combo)

        # Port
        layout.addWidget(QLabel("Local Port"))
        self.port_input = QLineEdit()
        default_port = self.config_manager.get("default_port", 3000) if self.config_manager else 3000
        self.port_input.setText(str(default_port))
        layout.addWidget(self.port_input)

        # Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        self.start_btn = QPushButton("Start Tunnel")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(self.validate_and_accept)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

    def validate_and_accept(self):
        port_text = self.port_input.text()
        if not port_text.isdigit() or not (1 <= int(port_text) <= 65535):
            QMessageBox.warning(self, "Invalid Port", "Please enter a valid port number (1-65535).")
            return
        
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip() or "app",
            "protocol": self.protocol_combo.currentText(),
            "port": int(self.port_input.text())
        }
