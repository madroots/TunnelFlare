from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor, QCursor
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
        is_published = False

        if is_running:
            if has_url:
                status = "ONLINE"
                dot_obj = "StatusDot"
                badge_obj = "BadgeOnline"
                is_published = True
            else:
                status = "STARTING"
                dot_obj = "StatusDotStarting"
                badge_obj = "BadgeStarting"
                is_published = False

        # Update Dot
        self.dot.setObjectName(dot_obj)
        self.dot.style().unpolish(self.dot)
        self.dot.style().polish(self.dot)
        
        # Update Badge
        self.badge.setText(status)
        self.badge.setObjectName(badge_obj)
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)
        
        # Update Visibility of URL box
        self.url_box.setVisible(has_url)
        if has_url:
            url = self.tunnel_data['public_url']
            display_url = url[:25] + "..." if len(url) > 30 else url
            self.url_text.setText(display_url)

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
        self.port_label = QLabel(f"🔌  PORT {self.tunnel_data['port']}")
        self.port_label.setObjectName("PortLabel")
        layout.addWidget(self.port_label)
        
        # Row 3: Inner URL Box
        layout.addSpacing(16) # Reduced from 18 to align with DetailView
        self.url_box = QFrame()
        self.url_box.setObjectName("UrlInner")
        url_layout = QHBoxLayout(self.url_box)
        url_layout.setContentsMargins(14, 12, 14, 12) # Slightly smaller padding
        
        self.url_text = QLabel("Initializing...")
        self.url_text.setObjectName("UrlText")
        
        # Using a more robust Unicode symbol for copy
        copy_icon = QLabel("⎙") # Refined copy/print symbol
        copy_icon.setStyleSheet("color: rgba(255, 255, 255, 0.3); font-size: 14px;")
        
        url_layout.addWidget(self.url_text)
        url_layout.addStretch()
        url_layout.addWidget(copy_icon)
        
        layout.addWidget(self.url_box)
        
        # Set initial state
        self.update_status(self.tunnel_data.get('running', False))

    def mousePressEvent(self, event):
        self.clicked.emit(self.tunnel_data)
        super().mousePressEvent(event)
