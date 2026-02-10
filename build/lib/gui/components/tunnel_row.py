from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor, QCursor
from PySide6.QtCore import Qt, Signal
from ..styles import Styles

class TunnelRow(QFrame):
    clicked = Signal(dict) # Emits tunnel data

    def __init__(self, tunnel_data, parent=None):
        super().__init__(parent)
        self.tunnel_data = tunnel_data
        self.setObjectName("TunnelRow")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(80)
        
        self.setup_ui()

    def update_status(self, is_running):
        self.tunnel_data['running'] = is_running
        color = Styles.THEME["status_live"] if is_running else Styles.THEME["status_dead"]
        
        # Update indicator
        effect = QGraphicsDropShadowEffect()
        effect.setBlurRadius(15)
        effect.setColor(QColor(color))
        effect.setOffset(0, 0)
        self.indicator.setGraphicsEffect(effect)
        
        # Update style of dot
        self.indicator.setStyleSheet(f"background-color: {color}; border-radius: 6px;")

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(15)

        # Status Indicator
        self.indicator = QLabel()
        self.indicator.setFixedSize(12, 12)
        layout.addWidget(self.indicator)
        
        # Text Info
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        self.name_label = QLabel(self.tunnel_data['name'])
        self.name_label.setStyleSheet(f"color: {Styles.THEME['text_main']}; font-weight: bold; font-size: 16px;")
        
        self.port_label = QLabel(f"Local Port: {self.tunnel_data['port']}")
        self.port_label.setStyleSheet(f"color: {Styles.THEME['text_dim']}; font-size: 12px;")
        
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.port_label)
        layout.addLayout(text_layout)
        
        layout.addStretch()
        
        # Arrow (Visual cue)
        arrow = QLabel("›")
        arrow.setStyleSheet(f"color: {Styles.THEME['text_dim']}; font-size: 24px;")
        layout.addWidget(arrow)
        
        # Initial status update
        # We assume data might have 'running' key if provided by view logic, or default false
        self.update_status(self.tunnel_data.get('running', False))

    def mousePressEvent(self, event):
        self.clicked.emit(self.tunnel_data)
        super().mousePressEvent(event)
