from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, Signal

class Sidebar(QFrame):
    create_tunnel_requested = Signal()
    refresh_requested = Signal()
    stop_all_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(250)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(20)

        # App Title
        title_label = QLabel("TunnelFlare")
        title_label.setObjectName("Title")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        # Primary Action
        self.create_btn = QPushButton("New Tunnel")
        self.create_btn.setObjectName("PrimaryButton")
        self.create_btn.setCursor(Qt.PointingHandCursor)
        self.create_btn.setMinimumHeight(40)
        self.create_btn.clicked.connect(self.create_tunnel_requested.emit)
        layout.addWidget(self.create_btn)

        # Secondary Actions
        self.refresh_btn = QPushButton("Refresh Status")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self.refresh_btn)

        self.stop_all_btn = QPushButton("Stop All Tunnels")
        self.stop_all_btn.setObjectName("DestructiveButton")
        self.stop_all_btn.setCursor(Qt.PointingHandCursor)
        self.stop_all_btn.clicked.connect(self.stop_all_requested.emit)
        layout.addWidget(self.stop_all_btn)

        # Spacer
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Footer
        footer = QLabel("v1.0.0")
        footer.setStyleSheet("color: #585b70;")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)
