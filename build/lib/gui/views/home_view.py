from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
from PySide6.QtCore import Qt, Signal
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
        layout.setContentsMargins(20, 40, 20, 20)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("My Tunnels")
        title.setObjectName("Title")
        
        add_btn = QPushButton("+")
        add_btn.setObjectName("PrimaryButton")
        add_btn.setFixedSize(40, 40)
        add_btn.clicked.connect(self.add_requested.emit)
        
        header.addWidget(title)
        header.addStretch()
        header.addWidget(add_btn)
        layout.addLayout(header)
        
        layout.addSpacing(10)
        
        # List
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)
        self.container_layout.setSpacing(10)
        
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
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {Styles.THEME['text_dim']}; margin-top: 50px;")
            self.container_layout.addWidget(empty)
            return

        for config in configs:
            # Merge runtime status
            is_running = config['name'] in active_names
            data = config.copy()
            data['running'] = is_running
            
            row = TunnelRow(data)
            row.clicked.connect(lambda d: self.tunnel_clicked.emit(d['name']))
            self.container_layout.addWidget(row)
