from PySide6.QtWidgets import QFrame, QVBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, Signal

class Sidebar(QFrame):
    create_tunnel_requested = Signal()
    refresh_requested = Signal()
    stop_all_requested = Signal()
    view_changed = Signal(str) # "active", "saved"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(250)
        self.current_view = "active"
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 30)
        layout.setSpacing(15)

        # App Title
        title_label = QLabel("TunnelFlare")
        title_label.setObjectName("Title")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        # Main Navigation
        self.nav_active = QPushButton("Active Tunnels")
        self.nav_active.setCheckable(True)
        self.nav_active.setChecked(True)
        self.nav_active.clicked.connect(lambda: self.switch_view("active"))
        layout.addWidget(self.nav_active)

        self.nav_saved = QPushButton("Saved Tunnels")
        self.nav_saved.setCheckable(True)
        self.nav_saved.clicked.connect(lambda: self.switch_view("saved"))
        layout.addWidget(self.nav_saved)

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
        footer = QLabel("v1.1.0")
        footer.setStyleSheet("color: #585b70;")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

    def switch_view(self, view):
        self.current_view = view
        if view == "active":
            self.nav_active.setChecked(True)
            self.nav_saved.setChecked(False)
        else:
            self.nav_active.setChecked(False)
            self.nav_saved.setChecked(True)
        self.view_changed.emit(view)

    def set_stop_all_enabled(self, enabled):
        self.stop_all_btn.setEnabled(enabled)
        # Optional: Change style if disabled
        opacity = "1" if enabled else "0.5"
        self.stop_all_btn.setStyleSheet(f"opacity: {opacity};")
