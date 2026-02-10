from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QMessageBox
from PySide6.QtCore import Qt, Signal

class SavedTunnelCard(QFrame):
    start_requested = Signal(dict)
    delete_requested = Signal(str) # name

    def __init__(self, tunnel_config, parent=None):
        super().__init__(parent)
        self.tunnel_config = tunnel_config
        self.setObjectName("Card")
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(15)

        # Info
        info_layout = QVBoxLayout()
        name_label = QLabel(self.tunnel_config['name'])
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        detail_label = QLabel(f"{self.tunnel_config['protocol']}://localhost:{self.tunnel_config['port']}")
        detail_label.setStyleSheet("color: #a6adc8;")
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(detail_label)
        layout.addLayout(info_layout)
        
        layout.addStretch()

        # Actions
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("PrimaryButton")
        self.start_btn.clicked.connect(lambda: self.start_requested.emit(self.tunnel_config))
        layout.addWidget(self.start_btn)

        self.delete_btn = QPushButton("🗑️")
        self.delete_btn.setFixedSize(40, 30)
        self.delete_btn.setObjectName("DestructiveButton")
        self.delete_btn.setToolTip("Remove from saved")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.tunnel_config['name']))
        layout.addWidget(self.delete_btn)


class SavedTunnelsView(QWidget):
    start_tunnel_requested = Signal(dict) # config
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QLabel("Saved Configurations")
        header.setObjectName("Subtitle")
        layout.addWidget(header)
        
        layout.addSpacing(10)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.container)
        
        layout.addWidget(self.scroll_area)
        
        self.refresh()

    def refresh(self):
        # Clear
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        saved = self.config_manager.get_saved_tunnels()
        
        if not saved:
            empty = QLabel("No saved tunnels found.\nPin active tunnels to save them here.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color: #7f849c; margin-top: 50px;")
            self.container_layout.addWidget(empty)
        else:
            for config in saved:
                card = SavedTunnelCard(config)
                card.start_requested.connect(self.start_tunnel_requested.emit)
                card.delete_requested.connect(self.delete_tunnel)
                self.container_layout.addWidget(card)

    def delete_tunnel(self, name):
        reply = QMessageBox.question(self, "Delete Saved Tunnel", f"Remove '{name}' from saved tunnels?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config_manager.remove_saved_tunnel(name)
            self.refresh()
