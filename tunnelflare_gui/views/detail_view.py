from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QApplication, QFrame
from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QClipboard, QIcon, QPixmap
from pathlib import Path
from ..styles import Styles
from ..components.tunnel_row import TunnelRow 
from ..dialogs.confirm_dialog import ConfirmDialog

from ..resources import RESOURCE_DIR

class DetailView(QWidget):
    back_requested = Signal()
    toggle_requested = Signal(str) # tunnel_name
    
    def __init__(self, tunnel_manager, parent=None):
        super().__init__(parent)
        self.tunnel_manager = tunnel_manager
        self.current_tunnel_name = None
        self.setup_ui()
        
        # Log poller
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.update_logs)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 40)
        layout.setSpacing(24)
        
        # Header (Back + Delete)
        header_layout = QHBoxLayout()
        self.back_btn = QPushButton(" Back")
        self.back_btn.setObjectName("BackButton")
        self.back_btn.setIcon(QIcon(str(RESOURCE_DIR / "back.svg")))
        self.back_btn.setIconSize(QSize(18, 18))
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.back_btn)
        
        header_layout.addStretch()
        
        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("BackButton") # Reuse ghost style
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setIcon(QIcon(str(RESOURCE_DIR / "delete.svg")))
        self.delete_btn.setIconSize(QSize(24, 24))
        self.delete_btn.clicked.connect(self.handle_delete)
        header_layout.addWidget(self.delete_btn)
        
        layout.addLayout(header_layout)
        
        # Unified Tunnel Card (Matching HomeView)
        self.status_card = QFrame()
        self.status_card.setObjectName("TunnelCard")
        card_layout = QVBoxLayout(self.status_card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(0)
        
        status_header = QHBoxLayout()
        status_header.setSpacing(10)
        self.dot = QLabel()
        self.dot.setObjectName("StatusDot")
        self.dot.setFixedSize(10, 10)
        
        self.name_label = QLabel("--") # Set in load_tunnel
        self.name_label.setObjectName("CardTitle")
        
        self.badge = QLabel("OFFLINE")
        self.badge.setObjectName("BadgeOffline")
        
        status_header.addWidget(self.dot)
        status_header.addWidget(self.name_label)
        status_header.addStretch()
        status_header.addWidget(self.badge)
        card_layout.addLayout(status_header)

        card_layout.addSpacing(10)
        port_layout = QHBoxLayout()
        port_layout.setSpacing(6)
        
        self.port_icon = QLabel()
        self.port_icon.setPixmap(QIcon(str(RESOURCE_DIR / "port.svg")).pixmap(16, 16))
        
        self.port_label = QLabel("PORT --")
        self.port_label.setObjectName("PortLabel")
        
        port_layout.addWidget(self.port_icon)
        port_layout.addWidget(self.port_label)
        port_layout.addStretch()
        card_layout.addLayout(port_layout)
        
        # URL Section (Insde the card to match HomeView)
        card_layout.addSpacing(16)
        self.url_container = QFrame()
        self.url_container.setObjectName("UrlInner")
        self.url_container.setCursor(Qt.PointingHandCursor)
        self.url_container.mousePressEvent = self.handle_url_click
        
        url_layout = QHBoxLayout(self.url_container)
        url_layout.setContentsMargins(14, 12, 14, 12)
        
        self.url_text = QLabel("tunnel is stopped")
        self.url_text.setObjectName("UrlText")
        
        self.copy_symbol = QLabel("⎙")
        self.copy_symbol.setStyleSheet("color: rgba(255, 255, 255, 0.3); font-size: 14px;")
        
        url_layout.addWidget(self.url_text)
        url_layout.addStretch()
        url_layout.addWidget(self.copy_symbol)
        card_layout.addWidget(self.url_container)
        
        layout.addWidget(self.status_card)

        # Action Buttons Row (Muted grey style)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        
        self.qr_btn = QPushButton(" QR Code")
        self.qr_btn.setIcon(QIcon(str(RESOURCE_DIR / "qr.svg")))
        self.qr_btn.setIconSize(QSize(20, 20))
        self.qr_btn.setMinimumHeight(48)
        self.qr_btn.setCursor(Qt.PointingHandCursor)
        self.qr_btn.clicked.connect(self.show_qr)
        
        self.open_btn = QPushButton(" Open Link")
        self.open_btn.setIcon(QIcon(str(RESOURCE_DIR / "open.svg")))
        self.open_btn.setIconSize(QSize(20, 20))
        self.open_btn.setMinimumHeight(48)
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(self.open_url)

        self.debug_btn = QPushButton(" Debug")
        self.debug_btn.setMinimumHeight(48)
        self.debug_btn.setCursor(Qt.PointingHandCursor)
        self.debug_btn.clicked.connect(self.show_debug)
        
        actions_layout.addWidget(self.qr_btn, 1)
        actions_layout.addWidget(self.open_btn, 1)
        actions_layout.addWidget(self.debug_btn, 1)
        layout.addLayout(actions_layout)
        
        # Toggle Button (Prominent at bottom)
        self.toggle_btn = QPushButton("Turn ON")
        self.toggle_btn.setObjectName("PrimaryAction")
        self.toggle_btn.setMinimumHeight(54)
        self.toggle_btn.clicked.connect(self.handle_toggle)
        layout.addWidget(self.toggle_btn)
        
        # Logs
        logs_header_layout = QHBoxLayout()
        logs_header_layout.setSpacing(6)
        
        logs_icon = QLabel()
        logs_icon.setPixmap(QIcon(str(RESOURCE_DIR / "logs.svg")).pixmap(16, 16))
        
        logs_label = QLabel("LIVE LOGS")
        logs_label.setObjectName("PortLabel")
        
        logs_header_layout.addWidget(logs_icon)
        logs_header_layout.addWidget(logs_label)
        logs_header_layout.addStretch()
        layout.addLayout(logs_header_layout)
        
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
    
    def handle_delete(self):
        target_name = self.current_tunnel_name
        dialog = ConfirmDialog(
            "Delete Tunnel",
            f"Are you sure you want to delete '{target_name}'? This action cannot be undone."
        )
        
        if dialog.exec():
            # 1. Stop if running
            active = self.tunnel_manager.get_active_tunnels()
            tunnel_id = next((t['id'] for t in active if t['name'] == target_name), None)
            if tunnel_id:
                self.tunnel_manager.stop_tunnel(tunnel_id)
            
            # 2. Delete from config
            self.tunnel_manager.config_manager.remove_tunnel(target_name)
            
            # 3. Go back
            self.back_requested.emit()

    def handle_url_click(self, event):
        self.copy_link()

    def load_tunnel(self, name):
        self.current_tunnel_name = name
        self.name_label.setText(name)
        # Find the port
        configs = self.tunnel_manager.config_manager.get_tunnels()
        config = next((c for c in configs if c['name'] == name), None)
        if config:
            self.port_label.setText(f"PORT {config['port']}")
            
        self.refresh_state()
        self.log_timer.start(1000)
    
    def refresh_state(self):
        if not self.current_tunnel_name: return
        
        active_tunnels = self.tunnel_manager.get_active_tunnels()
        tunnel_info = next((t for t in active_tunnels if t['name'] == self.current_tunnel_name), None)
        is_running = bool(tunnel_info)
        has_url = bool(tunnel_info.get('public_url')) if tunnel_info else False

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
        
        if is_running:
            # Only update button if it's enabled (not currently performing an action)
            if self.toggle_btn.isEnabled():
                self.toggle_btn.setText("Stop Tunnel")
                self.toggle_btn.setObjectName("DestructiveButton")
                self.toggle_btn.setProperty("is_running", True)
            
            if has_url:
                url = tunnel_info.get('public_url')
                self.url_text.setText(url)
                self.url_container.setVisible(True)
                self.qr_btn.setEnabled(True)
                self.open_btn.setEnabled(True)
            else:
                self.url_text.setText("Allocating URL...")
                self.url_container.setVisible(True)
                self.qr_btn.setEnabled(False)
                self.open_btn.setEnabled(False)
        else:
            if self.toggle_btn.isEnabled():
                self.toggle_btn.setText("Turn ON")
                self.toggle_btn.setObjectName("PrimaryAction")
                self.toggle_btn.setProperty("is_running", False)
            
            self.url_container.setVisible(False)
            self.qr_btn.setEnabled(False)
            self.open_btn.setEnabled(False)
            
        # Re-enable button if the background action is done
        is_btn_running = self.toggle_btn.property("is_running")
        # If button says it's running but it's not, or vice versa, and it was disabled (action in progress)
        if not self.toggle_btn.isEnabled():
             # If we were starting (is_running was False) and now it IS running
             if is_btn_running == False and is_running == True:
                 self.toggle_btn.setEnabled(True)
             # If we were stopping (is_running was True) and now it is NOT running
             elif is_btn_running == True and is_running == False:
                 self.toggle_btn.setEnabled(True)
             
        # Re-polish style for toggle button
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)
        
        # Opacity for card
        self.status_card.setProperty("offline", "false" if is_running else "true")
        self.status_card.style().unpolish(self.status_card)
        self.status_card.style().polish(self.status_card)

    def update_logs(self):
        if not self.current_tunnel_name: return
        logs = self.tunnel_manager.get_logs_by_name(self.current_tunnel_name)
        if logs:
            self.log_display.setPlainText(logs)
            self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())

    def handle_toggle(self):
        # We need to know port from config
        # This view doesn't have config access directly?
        # Better: emit signal to Main Window to handle logic, or pass config in load_tunnel.
        # Let's emit signal.
        self.toggle_requested.emit(self.current_tunnel_name)
        # Optimistic update or wait for refresh? Wait for refresh loop handled by main window usually.
        # But for UX response:
        QTimer.singleShot(200, self.refresh_state)

    def copy_link(self):
        text = self.url_text.text()
        if "http" in text:
            QApplication.clipboard().setText(text)
            self.copy_symbol.setText("✓")
            QTimer.singleShot(1500, lambda: self.copy_symbol.setText("⎙"))

    def open_url(self):
        text = self.url_text.text()
        if "http" in text:
            QDesktopServices.openUrl(QUrl(text))

    def show_debug(self):
        from ..dialogs.log_viewer import LogViewerDialog
        path = self.tunnel_manager.get_debug_log_path()
        dialog = LogViewerDialog(path, self)
        dialog.setWindowTitle("Internal Debug Logs")
        dialog.exec()

    def show_qr(self):
        text = self.url_text.text()
        if "http" in text:
             from ..dialogs.qr_code import QRCodeDialog
             dialog = QRCodeDialog(text, self.window())
             dialog.exec()
    
    def stop(self):
        self.log_timer.stop()
