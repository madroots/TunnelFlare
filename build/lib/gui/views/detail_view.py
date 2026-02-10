from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QApplication
from PySide6.QtCore import Qt, Signal, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QClipboard, QIcon
from pathlib import Path
from ..styles import Styles
from ..components.tunnel_row import TunnelRow 

RESOURCE_PATH = Path(__file__).parent.parent / "resources"

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
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header
        header_layout = QHBoxLayout()
        self.back_btn = QPushButton("← Back")
        self.back_btn.setObjectName("IconButton")
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.back_btn)
        
        self.title_label = QLabel("Tunnel Details")
        self.title_label.setObjectName("Title")
        header_layout.addStretch()
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Main Status Card
        self.status_card = QWidget() # Using layout to simulate card
        card_layout = QVBoxLayout()
        
        self.status_label = QLabel("OFFLINE")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 14px; color: {Styles.THEME['text_dim']}; letter-spacing: 1px;")
        card_layout.addWidget(self.status_label)
        
        self.toggle_btn = QPushButton("Turn ON")
        self.toggle_btn.setObjectName("PrimaryButton")
        self.toggle_btn.setMinimumHeight(50)
        self.toggle_btn.clicked.connect(self.handle_toggle)
        card_layout.addWidget(self.toggle_btn)
        
        layout.addLayout(card_layout)
        
        # URL Display
        self.url_label = QLabel("waiting for url...")
        self.url_label.setObjectName("UrlDisplay")
        self.url_label.setAlignment(Qt.AlignCenter)
        self.url_label.setCursor(Qt.PointingHandCursor)
        self.url_label.mousePressEvent = self.open_url
        layout.addWidget(self.url_label)
        
        # Actions Row
        actions = QHBoxLayout()
        self.copy_btn = QPushButton(" Copy Link")
        self.copy_btn.setObjectName("IconButton")
        self.copy_btn.setIcon(QIcon(str(RESOURCE_PATH / "copy.svg")))
        self.copy_btn.clicked.connect(self.copy_link)
        
        self.qr_btn = QPushButton(" QR Code")
        self.qr_btn.setObjectName("IconButton")
        self.qr_btn.setIcon(QIcon(str(RESOURCE_PATH / "qr.svg")))
        self.qr_btn.clicked.connect(self.show_qr)

        actions.addWidget(self.copy_btn)
        actions.addWidget(self.qr_btn)
        layout.addLayout(actions)
        
        # Logs
        layout.addWidget(QLabel("Live Logs", objectName="Subtitle"))
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
    
    def load_tunnel(self, name):
        self.current_tunnel_name = name
        self.title_label.setText(name)
        self.refresh_state()
        self.log_timer.start(1000)
    
    def refresh_state(self):
        if not self.current_tunnel_name: return
        
        active_tunnels = self.tunnel_manager.get_active_tunnels()
        # Find if running
        tunnel_info = next((t for t in active_tunnels if t['name'] == self.current_tunnel_name), None)
        
        if tunnel_info:
            self.toggle_btn.setText("Stop Tunnel")
            self.toggle_btn.setObjectName("DestructiveButton")
            self.status_label.setText("ONLINE")
            self.status_label.setStyleSheet(f"color: {Styles.THEME['status_live']}; font-weight: bold;")
            
            url = tunnel_info.get('public_url')
            if url:
                self.url_label.setText(url)
                self.url_label.setEnabled(True)
            else:
                self.url_label.setText("Allocating URL...")
                self.url_label.setEnabled(False)
        else:
            self.toggle_btn.setText("Turn ON")
            self.toggle_btn.setObjectName("PrimaryButton")
            self.status_label.setText("OFFLINE")
            self.status_label.setStyleSheet(f"color: {Styles.THEME['text_dim']};")
            self.url_label.setText("Tunnel is stopped")
            self.url_label.setEnabled(False)
            
        # Re-polish style
        self.toggle_btn.style().unpolish(self.toggle_btn)
        self.toggle_btn.style().polish(self.toggle_btn)

    def update_logs(self):
        if not self.current_tunnel_name: return
        # Get logs from manager
        # Optimization: We need to know the ID to get logs, but we only have name.
        # Manager should probably support get_logs_by_name or we lookup ID.
        logs = self.tunnel_manager.get_logs_by_name(self.current_tunnel_name)
        if logs:
            self.log_display.setPlainText(logs)
            self.log_display.verticalScrollBar().setValue(self.log_display.verticalScrollBar().maximum())
        else:
            if self.log_display.toPlainText() != "":
                # Don't clear if stopped? Maybe user wants to see last logs.
                # For now keep it.
                pass

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
        text = self.url_label.text()
        if "http" in text:
            QApplication.clipboard().setText(text)
            self.copy_btn.setText("Copied!")
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy Link"))

    def open_url(self, event):
        text = self.url_label.text()
        if "http" in text:
            QDesktopServices.openUrl(QUrl(text))

    def show_qr(self):
        text = self.url_label.text()
        if "http" in text:
             from ..dialogs.qr_code import QRCodeDialog
             dialog = QRCodeDialog(text, self.window())
             dialog.exec()
    
    def stop(self):
        self.log_timer.stop()
