from pathlib import Path

RESOURCE_PATH = Path(__file__).parent / "resources"

from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow, QStackedWidget, QSystemTrayIcon, 
    QMenu, QApplication, QMessageBox
)
from backend.tunnel_manager import TunnelManager
from backend.config_manager import ConfigManager
from .views.home_view import HomeView
from .views.detail_view import DetailView
from .dialogs.create_tunnel import CreateTunnelDialog
from .styles import Styles

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        
        self.config_manager = ConfigManager()
        self.tunnel_manager = TunnelManager()
        
        self.setup_ui()
        self.setup_tray()
        
        # Navigation Stack
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack) # self.stack is the central widget
        
        # Views
        self.home_view = HomeView(self.config_manager, self.tunnel_manager)
        self.detail_view = DetailView(self.tunnel_manager)
        
        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.detail_view)
        
        # Signals
        self.home_view.add_requested.connect(self.show_add_dialog)
        self.home_view.tunnel_clicked.connect(self.go_to_detail)
        self.detail_view.back_requested.connect(self.go_home)
        self.detail_view.toggle_requested.connect(self.toggle_tunnel)
        
        # Loop
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_current_view)
        self.refresh_timer.start(2000)
        
        self.refresh_current_view()

    def setup_ui(self):
        self.setWindowTitle("TunnelFlare")
        self.setFixedWidth(420)
        self.setMinimumHeight(700)
    
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        try:
             # Try custom icon
             icon = QIcon(str(RESOURCE_PATH / "tray.svg"))
             if icon.isNull():
                 # Fallback
                 icon = QApplication.style().standardIcon(QApplication.style().SP_ComputerIcon)
             self.tray_icon.setIcon(icon)
        except:
             pass
        
        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        
        menu.addAction(show_action)
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def refresh_current_view(self):
        if self.stack.currentWidget() == self.home_view:
            self.home_view.refresh()
        elif self.stack.currentWidget() == self.detail_view:
            self.detail_view.refresh_state()

    def go_to_detail(self, name):
        self.detail_view.load_tunnel(name)
        self.stack.setCurrentWidget(self.detail_view)

    def go_home(self):
        self.detail_view.stop() # Stop logs
        self.stack.setCurrentWidget(self.home_view)
        self.home_view.refresh()

    def show_add_dialog(self):
        dialog = CreateTunnelDialog(self, self.config_manager)
        if dialog.exec():
            data = dialog.get_data()
            self.config_manager.add_tunnel(data['name'], data['port'])
            self.home_view.refresh() # Immediate update

    def toggle_tunnel(self, name):
        import threading
        # Determine if we should start or stop
        active = self.tunnel_manager.get_active_tunnels()
        tunnel_id = next((t['id'] for t in active if t['name'] == name), None)
        
        # Immediate UI Feedback
        if tunnel_id:
            self.detail_view.toggle_btn.setText("Stopping...")
            self.detail_view.toggle_btn.setEnabled(False)
        else:
            self.detail_view.toggle_btn.setText("Starting...")
            self.detail_view.toggle_btn.setEnabled(False)

        def run_action():
            try:
                if tunnel_id:
                    self.tunnel_manager.stop_tunnel(tunnel_id)
                else:
                    configs = self.config_manager.get_tunnels()
                    config = next((c for c in configs if c['name'] == name), None)
                    if config:
                        self.tunnel_manager.start_tunnel(config['name'], config['port'])
            except Exception as e:
                # We could signal an error back, but for now just log/warn
                print(f"Error toggling tunnel {name}: {e}")
            
            # The refresh_timer will eventually pick up the new state
        
        thread = threading.Thread(target=run_action, daemon=True)
        thread.start()

    def closeEvent(self, event):
        # Minimize to tray instead of closing?
        # User requested "System Tray Integration: It allows users to close the GUI while keeping the dev-tunnel running"
        # So ignore close, hide.
        if self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("TunnelFlare", "Running in background", QSystemTrayIcon.Information, 2000)
        else:
            super().closeEvent(event)
