from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtCore import Qt, Signal

from ..resources import RESOURCE_DIR


def status_style(tunnel_info):
    """(badge text, dot style, badge style) for a get_active_tunnels() entry; None = stopped."""
    if not tunnel_info:
        return "OFFLINE", "StatusDotOffline", "BadgeOffline"
    if tunnel_info.get("status") == "Running":
        return "ONLINE", "StatusDot", "BadgeOnline"
    if tunnel_info.get("status") == "Reconnecting":
        return "RECONNECTING", "StatusDotStarting", "BadgeStarting"
    return "STARTING", "StatusDotStarting", "BadgeStarting"


def restyle(widget, object_name):
    """Switch a widget to another stylesheet selector, repolishing only on change."""
    if widget.objectName() != object_name:
        widget.setObjectName(object_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class TunnelRow(QFrame):
    clicked = Signal(str)  # tunnel name

    def __init__(self, config, tunnel_info=None, parent=None):
        super().__init__(parent)
        self.setObjectName("TunnelCard")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFocusPolicy(Qt.StrongFocus)  # Tab to a card; Enter or Space opens it
        self.name = None
        self.setup_ui()
        self.set_data(config, tunnel_info)

    def setup_ui(self):
        # Card padding 18px
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        # Row 1: dot + title + badge
        header = QHBoxLayout()
        header.setSpacing(10)
        
        self.dot = QLabel()
        self.dot.setObjectName("StatusDotOffline")
        self.dot.setFixedSize(10, 10)
        
        self.name_label = QLabel()
        self.name_label.setObjectName("CardTitle")
        
        self.badge = QLabel()
        self.badge.setObjectName("BadgeOffline")
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
        self.port_icon.setPixmap(QIcon(str(RESOURCE_DIR / "port.svg")).pixmap(16, 16))
        self.port_icon.setFixedSize(16, 16)
        self.port_icon.setScaledContents(True)
        
        self.port_label = QLabel()
        self.port_label.setObjectName("PortLabel")
        
        port_layout.addWidget(self.port_icon)
        port_layout.addWidget(self.port_label)
        port_layout.addStretch()
        layout.addLayout(port_layout)

    def set_data(self, config, tunnel_info=None):
        """Show `config` with its runtime state (`tunnel_info` is None when stopped)."""
        self.name = config["name"]
        port_text = f"PORT {config['port']}"
        badge_text, dot_style, badge_style = status_style(tunnel_info)
        for label, text in ((self.name_label, self.name), (self.port_label, port_text), (self.badge, badge_text)):
            if label.text() != text:
                label.setText(text)
        restyle(self.dot, dot_style)
        restyle(self.badge, badge_style)
        offline = "false" if tunnel_info else "true"
        if self.property("offline") != offline:
            self.setProperty("offline", offline)
            self.style().unpolish(self)
            self.style().polish(self)
        self.setAccessibleName(f"{self.name}, port {config['port']}, {badge_text.lower()}")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.name)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit(self.name)
        else:
            super().keyPressEvent(event)
