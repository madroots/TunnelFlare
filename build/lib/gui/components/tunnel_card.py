from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QClipboard

class TunnelCard(QFrame):
    stop_requested = Signal(str) # tunnel_id
    logs_requested = Signal(str) # tunnel_id

    def __init__(self, tunnel_data, parent=None):
        super().__init__(parent)
        self.tunnel_data = tunnel_data
        self.setObjectName("Card")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header: Name and Status
        header_layout = QHBoxLayout()
        self.name_label = QLabel(self.tunnel_data['name'])
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.status_label = QLabel(self.tunnel_data['status'])
        status_color = "StatusRunning" if self.tunnel_data['status'] == "Running" else "StatusInitializing"
        self.status_label.setObjectName(status_color)
        
        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        layout.addLayout(header_layout)

        # Info: Local Port
        info_layout = QHBoxLayout()
        local_info = QLabel(f"Local: {self.tunnel_data['protocol']}://localhost:{self.tunnel_data['port']}")
        local_info.setStyleSheet("color: #a6adc8;")
        info_layout.addWidget(local_info)
        layout.addLayout(info_layout)

        # Public URL
        if self.tunnel_data.get('public_url'):
            url_layout = QHBoxLayout()
            self.url_btn = QPushButton(self.tunnel_data['public_url'])
            self.url_btn.setObjectName("LinkButton")
            self.url_btn.setCursor(Qt.PointingHandCursor)
            self.url_btn.clicked.connect(self.copy_url)
            
            copy_hint = QLabel("(Click to copy)")
            copy_hint.setStyleSheet("color: #585b70; font-size: 12px;")
            
            url_layout.addWidget(self.url_btn)
            url_layout.addWidget(copy_hint)
            
            # QR Code Button
            self.qr_btn = QPushButton("📱")
            self.qr_btn.setFixedSize(30, 30)
            self.qr_btn.setToolTip("Show QR Code")
            self.qr_btn.clicked.connect(self.show_qr_code)
            url_layout.addWidget(self.qr_btn)
            
            url_layout.addStretch()
            layout.addLayout(url_layout)
        else:
            loading_label = QLabel("Waiting for public URL...")
            loading_label.setStyleSheet("color: #f9e2af; font-style: italic;")
            layout.addWidget(loading_label)

        # Actions
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.logs_btn = QPushButton("Logs")
        self.logs_btn.clicked.connect(lambda: self.logs_requested.emit(self.tunnel_data['id']))
        
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("DestructiveButton")
        self.stop_btn.clicked.connect(lambda: self.stop_requested.emit(self.tunnel_data['id']))

        action_layout.addWidget(self.logs_btn)
        action_layout.addWidget(self.stop_btn)
        layout.addLayout(action_layout)

    def copy_url(self):
        if self.tunnel_data.get('public_url'):
            clipboard = QApplication.clipboard()
            clipboard.setText(self.tunnel_data['public_url'])
            self.url_btn.setText("Copied!")
    
    def show_qr_code(self):
        if self.tunnel_data.get('public_url'):
            from ..dialogs.qr_code import QRCodeDialog
            dialog = QRCodeDialog(self.tunnel_data['public_url'], self)
            dialog.exec()
