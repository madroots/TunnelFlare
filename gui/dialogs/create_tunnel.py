from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QMessageBox
from PySide6.QtCore import Qt
from ..styles import Styles

class CreateTunnelDialog(QDialog):
    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("Add Tunnel")
        self.setFixedWidth(350)
        self.setStyleSheet(Styles.STYLESHEET)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30,30,30,30)
        
        layout.addWidget(QLabel("Tunnel Name", objectName="Subtitle"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. backend-api")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Local Port", objectName="Subtitle"))
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("3000")
        layout.addWidget(self.port_input)

        # Buttons
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet(f"background: transparent; color: {Styles.THEME['text_dim']}; border: 1px solid {Styles.THEME['bg_card']}; padding: 8px;")
        
        self.save_btn = QPushButton("Add Tunnel")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self.validate_and_accept)
        
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
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
