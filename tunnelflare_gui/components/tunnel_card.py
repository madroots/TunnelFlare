from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication, QStyle
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QCursor

class TunnelCard(QFrame):
    stop_requested = Signal(str) # tunnel_id
    logs_requested = Signal(str) # tunnel_id
    pin_requested = Signal(dict) # tunnel_data

    def __init__(self, tunnel_data, parent=None):
        super().__init__(parent)
        self.tunnel_data = tunnel_data
        self.setObjectName("Card")
        self.setup_ui()

    def update_data(self, new_data):
        # Update fields if changed
        if new_data['status'] != self.tunnel_data['status']:
            self.tunnel_data['status'] = new_data['status']
            status_color = "StatusRunning" if self.tunnel_data['status'] == "Running" else "StatusInitializing"
            self.status_label.setText(self.tunnel_data['status'])
            self.status_label.setObjectName(status_color)
            self.status_label.setStyleSheet("") # Force re-style

        if new_data.get('public_url') != self.tunnel_data.get('public_url'):
            self.tunnel_data['public_url'] = new_data.get('public_url')
            # Reconstruct URL section
            self.rebuild_url_section()

    def setup_ui(self):
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setSpacing(10)
        
        # Header: Name, Status, Pin
        header_layout = QHBoxLayout()
        self.name_label = QLabel(self.tunnel_data['name'])
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        self.status_label = QLabel(self.tunnel_data['status'])
        status_color = "StatusRunning" if self.tunnel_data['status'] == "Running" else "StatusInitializing"
        self.status_label.setObjectName(status_color)
        
        self.pin_btn = QPushButton("📌") # Pin icon
        self.pin_btn.setFixedSize(30, 30)
        self.pin_btn.setToolTip("Pin this tunnel configuration")
        self.pin_btn.clicked.connect(lambda: self.pin_requested.emit(self.tunnel_data))
        self.pin_btn.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; font-size: 16px; }
            QPushButton:hover { background-color: #313244; border-radius: 4px; }
        """)

        header_layout.addWidget(self.name_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.pin_btn)
        self.layout_main.addLayout(header_layout)

        # Info: Local Port
        info_layout = QHBoxLayout()
        local_info = QLabel(f"Local: {self.tunnel_data['protocol']}://localhost:{self.tunnel_data['port']}")
        local_info.setStyleSheet("color: #a6adc8;")
        info_layout.addWidget(local_info)
        self.layout_main.addLayout(info_layout)

        # Public URL Section Container
        self.url_container = QWidget()
        self.url_layout = QVBoxLayout(self.url_container)
        self.url_layout.setContentsMargins(0,0,0,0)
        self.layout_main.addWidget(self.url_container)
        
        self.rebuild_url_section()

        # Actions
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        
        self.logs_btn = QPushButton(" Logs")
        self.logs_btn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView)) # Use std icon as fallback
        self.logs_btn.clicked.connect(lambda: self.logs_requested.emit(self.tunnel_data['id']))
        
        self.stop_btn = QPushButton(" Stop")
        self.stop_btn.setObjectName("DestructiveButton")
        self.stop_btn.clicked.connect(lambda: self.stop_requested.emit(self.tunnel_data['id']))

        action_layout.addWidget(self.logs_btn)
        action_layout.addWidget(self.stop_btn)
        self.layout_main.addLayout(action_layout)

    def rebuild_url_section(self):
        # Clear existing
        # Pythonic way to clear layout
        if self.url_layout.count():
            for i in reversed(range(self.url_layout.count())): 
                widget = self.url_layout.itemAt(i).widget()
                layout = self.url_layout.itemAt(i).layout()
                if widget: widget.deleteLater()
                if layout: 
                     # Recursively delete layouts? complex. Just delete items.
                     # Simplified:
                     pass
            # Force clean
            while self.url_layout.count():
                item = self.url_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
                # If it's a layout, we have issues. But we added HBox.
                # HBox is an item. layout() returns it.
        
        # Add new
        if self.tunnel_data.get('public_url'):
            url_row = QHBoxLayout()
            
            # Clickable URL
            url_btn = QPushButton(self.tunnel_data['public_url'])
            url_btn.setObjectName("LinkButton")
            url_btn.setCursor(Qt.PointingHandCursor)
            url_btn.setToolTip("Open in Browser")
            url_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.tunnel_data['public_url'])))
            
            # Copy Button
            copy_btn = QPushButton("📋")
            copy_btn.setFixedSize(30,30)
            copy_btn.setToolTip("Copy URL")
            copy_btn.setCursor(Qt.PointingHandCursor)
            copy_btn.clicked.connect(self.copy_url)
            
            # QR Button
            qr_btn = QPushButton("📱")
            qr_btn.setFixedSize(30,30)
            qr_btn.setToolTip("Show QR Code")
            qr_btn.setCursor(Qt.PointingHandCursor)
            qr_btn.clicked.connect(self.show_qr_code)
            
            url_row.addWidget(url_btn)
            url_row.addStretch()
            url_row.addWidget(copy_btn)
            url_row.addWidget(qr_btn)
            
            self.url_layout.addLayout(url_row)
        else:
            loading_label = QLabel("Waiting for public URL...")
            loading_label.setStyleSheet("color: #f9e2af; font-style: italic;")
            self.url_layout.addWidget(loading_label)

    def copy_url(self):
        if self.tunnel_data.get('public_url'):
            clipboard = QApplication.clipboard()
            clipboard.setText(self.tunnel_data['public_url'])
    
    def show_qr_code(self):
        if self.tunnel_data.get('public_url'):
            from ..dialogs.qr_code import QRCodeDialog
            dialog = QRCodeDialog(self.tunnel_data['public_url'], self.window()) 
            dialog.exec()
