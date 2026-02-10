from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from ..components.tunnel_row import TunnelRow
from ..styles import Styles

class HomeView(QWidget):
    add_requested = Signal()
    tunnel_clicked = Signal(str) # name

    def __init__(self, config_manager, tunnel_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.tunnel_manager = tunnel_manager
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        # Standardized Margin: Top 28, Side 24, Bottom 40
        layout.setContentsMargins(24, 28, 24, 40)
        layout.setSpacing(0)
        
        # Header
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2) # Tight spacing between title and subtitle
        header_text.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("TunnelFlare")
        title.setObjectName("AppTitle")
        
        subtitle = QLabel("Manage your active environments")
        subtitle.setObjectName("AppSubtitle")
        
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        
        add_btn = QPushButton()
        add_btn.setObjectName("AddButton")
        add_btn.setFixedSize(46, 46)
        add_btn.setCursor(Qt.PointingHandCursor)
        
        from pathlib import Path
        resource_path = Path(__file__).parent.parent / "resources"
        add_btn.setIcon(QIcon(str(resource_path / "add.svg")))
        add_btn.setIconSize(QSize(30, 30))
        
        add_btn.clicked.connect(self.add_requested.emit)
        
        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(add_btn)
        layout.addLayout(header)
        
        layout.addSpacing(26)
        
        # List Container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)
        self.container_layout.setSpacing(26) # Matching .card margin-top
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

    def refresh(self):
        # Rebuild list
        # Optimization: Map running tunnels first
        active_tunnels = self.tunnel_manager.get_active_tunnels()
        active_names = {t['name'] for t in active_tunnels}
        
        # Clear
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        configs = self.config_manager.get_tunnels()
        
        if not configs:
            empty = QLabel("No tunnels yet.\nClick + to add one.")
            empty.setObjectName("Subtitle") # Use standardized object name
            self.container_layout.addWidget(empty)
            return

        for config in configs:
            # Merge runtime status and public URL
            tunnel_info = next((t for t in active_tunnels if t['name'] == config['name']), None)
            is_running = bool(tunnel_info)
            
            data = config.copy()
            data['running'] = is_running
            if tunnel_info:
                data['public_url'] = tunnel_info.get('public_url')
            
            row = TunnelRow(data)
            row.clicked.connect(lambda d: self.tunnel_clicked.emit(d['name']))
            self.container_layout.addWidget(row)
