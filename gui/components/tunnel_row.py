from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor, QCursor, QIcon, QPixmap
from PySide6.QtCore import Qt, Signal
from ..styles import Styles

class TunnelRow(QFrame):
    clicked = Signal(dict) # Emits tunnel data

    def __init__(self, tunnel_data, parent=None):
        super().__init__(parent)
        self.tunnel_data = tunnel_data
        self.setObjectName("TunnelCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        # Remove fixed height to allow expansion for URL box
        
        self.setup_ui()

    def update_status(self, is_running):
        self.tunnel_data['running'] = is_running
        has_url = bool(self.tunnel_data.get('public_url'))
        
        status = "OFFLINE"
        dot_obj = "StatusDotOffline"
        badge_obj = "BadgeOffline"

        if is_running:
            if has_url:
                status = "ONLINE"
                dot_obj = "StatusDot"
                badge_obj = "BadgeOnline"
            else:
                status = "STARTING"
                dot_obj = "StatusDotStarting"
                badge_obj = "BadgeStarting"

        # Update Dot
        self.dot.setObjectName(dot_obj)
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)
        
        # Update Badge
        self.badge.setText(status)
        self.badge.setObjectName(badge_obj)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        
        # Update Card opacity
        # If it's starting, maybe keep it full opacity or slightly dimmed?
        # User said "wait with online status", I'll consider it "not offline" once starting.
        self.setProperty("offline", "false" if is_running else "true")
        self.style().unpolish(self)
        self.style().polish(self)

    def setup_ui(self):
        # Card padding 18px
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        # Row 1: dot + title + badge
        header = QHBoxLayout()
        header.setSpacing(10)
        
        self.dot = QLabel()
        self.dot.setObjectName("StatusDot")
        self.dot.setFixedSize(10, 10)
        
        self.name_label = QLabel(self.tunnel_data['name'])
        self.name_label.setObjectName("CardTitle")
        
        self.badge = QLabel("ONLINE")
        self.badge.setObjectName("BadgeOnline")
        self.badge.setAlignment(Qt.AlignCenter)
        
        header.addWidget(self.dot)
        header.addWidget(self.name_label)
        header.addStretch()
        header.addWidget(self.badge)
        layout.addLayout(header)
        
        # Row 2: Port
        layout.addSpacing(10)
        port_layout = QHBoxLayout()
        port_layout.setSpacing(6)
        
        self.port_icon = QLabel()
        from pathlib import Path
        resource_path = Path(__file__).parent.parent / "resources"
        # We can use QIcon + pixmap for simpler label display
        pixmap = QIcon(str(resource_path / "port.svg")).pixmap(16, 16)
        self.port_icon.setPixmap(pixmap)
        self.port_icon.setFixedSize(16, 16)
        self.port_icon.setScaledContents(True)
        
        self.port_label = QLabel(f"PORT {self.tunnel_data['port']}")
        self.port_label.setObjectName("PortLabel")
        
        port_layout.addWidget(self.port_icon)
        port_layout.addWidget(self.port_label)
        port_layout.addStretch()
        layout.addLayout(port_layout)
        
        # Set initial state
        self.update_status(self.tunnel_data.get('running', False))

    def mousePressEvent(self, event):
        self.clicked.emit(self.tunnel_data)
        super().mousePressEvent(event)
