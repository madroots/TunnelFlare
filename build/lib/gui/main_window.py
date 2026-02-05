from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QScrollArea, QMessageBox, QApplication
from PySide6.QtCore import QTimer, Qt
from backend.tunnel_manager import TunnelManager
from backend.config_manager import ConfigManager
from .components.sidebar import Sidebar
from .components.tunnel_card import TunnelCard
from .dialogs.create_tunnel import CreateTunnelDialog
from .dialogs.log_viewer import LogViewerDialog
from .styles import Styles

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TunnelFlare")
        self.resize(1000, 700)
        
        self.config_manager = ConfigManager()
        self.tunnel_manager = TunnelManager()
        
        self.setup_ui()
        self.check_dependencies()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_tunnels)
        self.refresh_timer.start(3000) # 3 seconds
        
        # Initial stats
        self.refresh_tunnels()

    def setup_ui(self):
        # Apply Styles
        self.setStyleSheet(Styles.STYLESHEET)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        self.sidebar.create_tunnel_requested.connect(self.show_create_tunnel_dialog)
        self.sidebar.refresh_requested.connect(self.refresh_tunnels)
        self.sidebar.stop_all_requested.connect(self.stop_all_tunnels)
        main_layout.addWidget(self.sidebar)

        # Content Area
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(30, 30, 30, 30)
        
        # Header (Optional, or just use ScrollArea directly)
        
        # Scroll Area for Tunnels
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.tunnels_container = QWidget()
        self.tunnels_layout = QVBoxLayout(self.tunnels_container)
        self.tunnels_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.tunnels_container)
        
        content_layout.addWidget(self.scroll_area)
        main_layout.addWidget(content_area)

    def check_dependencies(self):
        if not self.tunnel_manager.check_dependencies():
            QMessageBox.critical(self, "Missing Dependency", "cloudflared is not installed. Please install it to use this application.")
            # We don't exit, but functionality will fail.

    def refresh_tunnels(self):
        # Get current data
        tunnels = self.tunnel_manager.get_active_tunnels()
        
        # Clear existing items (inefficient but safe for now)
        # Optimization: Diff Update could be better but complexity is higher.
        while self.tunnels_layout.count():
            item = self.tunnels_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        if not tunnels:
            empty_label = QLabel("No active tunnels. Start one to get going!")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #7f849c; font-size: 16px; margin-top: 50px;")
            self.tunnels_layout.addWidget(empty_label)
        else:
            for tunnel in tunnels:
                card = TunnelCard(tunnel)
                card.stop_requested.connect(self.stop_tunnel)
                card.logs_requested.connect(self.show_logs)
                self.tunnels_layout.addWidget(card)

    def show_create_tunnel_dialog(self):
        dialog = CreateTunnelDialog(self, self.config_manager)
        if dialog.exec():
            data = dialog.get_data()
            try:
                self.tunnel_manager.start_tunnel(data['name'], data['port'], data['protocol'])
                self.refresh_tunnels()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to start tunnel: {str(e)}")

    def stop_tunnel(self, tunnel_id):
        if self.tunnel_manager.stop_tunnel(tunnel_id):
            self.refresh_tunnels()
        else:
            QMessageBox.warning(self, "Error", "Failed to stop tunnel or it was already stopped.")

    def stop_all_tunnels(self):
        reply = QMessageBox.question(self, "Stop All", "Are you sure you want to stop ALL running tunnels?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.tunnel_manager.stop_all()
            self.refresh_tunnels()

    def show_logs(self, tunnel_id):
        log_file = self.tunnel_manager.logs_dir / f"{tunnel_id}.log"
        dialog = LogViewerDialog(str(log_file), self)
        dialog.exec()
