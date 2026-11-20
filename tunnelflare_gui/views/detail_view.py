from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QApplication, QFrame, QSizePolicy
from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon
from ..components.tunnel_row import restyle, status_style
from ..dialogs.confirm_dialog import ConfirmDialog

from ..resources import RESOURCE_DIR

# Statuses in which the public URL has been reachable at least once
REACHABLE = ("Running", "Reconnecting")


class ElidedLabel(QLabel):
    """One-line label that shortens text that doesn't fit with … in the middle."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text):
        self._full_text = text
        self._elide()

    def text(self):
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        self.ensurePolished()  # measure with the stylesheet font
        super().setText(self.fontMetrics().elidedText(self._full_text, Qt.ElideMiddle, max(0, self.width())))


class DetailView(QWidget):
    back_requested = Signal()
    toggle_requested = Signal(str) # tunnel_name
    edit_requested = Signal(str) # tunnel_name
    
    def __init__(self, tunnel_manager, parent=None):
        super().__init__(parent)
        self.tunnel_manager = tunnel_manager
        self.current_tunnel_name = None
        self._busy = False
        self._shown_logs = None
        self._public_url = None
        self.setup_ui()
        
        # Log poller
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.update_logs)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 28, 24, 40)
        layout.setSpacing(24)
        
        # Header (Back + Edit + Delete)
        header_layout = QHBoxLayout()
        self.back_btn = QPushButton(" Back")
        self.back_btn.setObjectName("BackButton")
        self.back_btn.setIcon(QIcon(str(RESOURCE_DIR / "back.svg")))
        self.back_btn.setIconSize(QSize(18, 18))
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header_layout.addWidget(self.back_btn)
        
        header_layout.addStretch()

        self.edit_btn = QPushButton()
        self.edit_btn.setObjectName("BackButton") # Reuse ghost style
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.setIcon(QIcon(str(RESOURCE_DIR / "edit.svg")))
        self.edit_btn.setIconSize(QSize(24, 24))
        self.edit_btn.setAccessibleName("Edit tunnel")
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.current_tunnel_name))
        header_layout.addWidget(self.edit_btn)
        header_layout.addSpacing(14)
        
        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("BackButton") # Reuse ghost style
        self.delete_btn.setCursor(Qt.PointingHandCursor)
        self.delete_btn.setIcon(QIcon(str(RESOURCE_DIR / "delete.svg")))
        self.delete_btn.setIconSize(QSize(24, 24))
        self.delete_btn.setToolTip("Delete tunnel")
        self.delete_btn.setAccessibleName("Delete tunnel")
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
        self.dot.setObjectName("StatusDotOffline")
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
        self.url_container.setToolTip("Copy link")
        self.url_container.mousePressEvent = self.handle_url_click
        
        url_layout = QHBoxLayout(self.url_container)
        url_layout.setContentsMargins(14, 12, 14, 12)
        
        self.url_text = ElidedLabel("tunnel is stopped")
        self.url_text.setObjectName("UrlText")
        
        self.copy_symbol = QLabel("⎙")
        self.copy_symbol.setStyleSheet("color: rgba(255, 255, 255, 0.3); font-size: 14px;")
        
        url_layout.addWidget(self.url_text, 1)
        url_layout.addWidget(self.copy_symbol)
        card_layout.addWidget(self.url_container)
        
        # Never squeeze the card on short windows; the log view gives up the space
        self.status_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
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
        
        actions_layout.addWidget(self.qr_btn, 1)
        actions_layout.addWidget(self.open_btn, 1)
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
        if self._busy:
            return
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
        config = self.tunnel_manager.config_manager.get_tunnel(name)
        if config:
            details = [f"PORT {config['port']}"]
            if config.get("protocol") == "https":
                details.append("HTTPS")
            if config.get("rewrite_host"):
                details.append("HOST: LOCALHOST")
            self.port_label.setText("  ·  ".join(details))
        self._shown_logs = None
        self.log_display.clear()
        self.refresh_state()
        self.update_logs()
        self.log_timer.start(1000)
    
    def refresh_state(self, active_tunnels=None):
        if not self.current_tunnel_name: return
        
        if active_tunnels is None:
            active_tunnels = self.tunnel_manager.get_active_tunnels()
        tunnel_info = next((t for t in active_tunnels if t['name'] == self.current_tunnel_name), None)
        is_running = bool(tunnel_info)
        self._public_url = tunnel_info.get('public_url') if tunnel_info else None
        reachable = bool(self._public_url) and tunnel_info.get('status') in REACHABLE

        status, dot_style, badge_style = status_style(tunnel_info)
        restyle(self.dot, dot_style)
        if self.badge.text() != status:
            self.badge.setText(status)
        restyle(self.badge, badge_style)
        
        if is_running:
            # Only update button if it's enabled (not currently performing an action)
            if not self._busy:
                self.toggle_btn.setText("Stop Tunnel")
                restyle(self.toggle_btn, "DestructiveButton")
            # The scheme adds nothing here; dropping it leaves room for the tunnel's name
            self.url_text.setText(self._public_url.removeprefix("https://") if self._public_url else "Allocating URL...")
            self.url_text.setToolTip(self._public_url or "")
            self.url_container.setVisible(True)
        else:
            if not self._busy:
                self.toggle_btn.setText("Turn ON")
                restyle(self.toggle_btn, "PrimaryAction")
            self.url_container.setVisible(False)
        # The link only works once cloudflared has connected to Cloudflare
        self.qr_btn.setEnabled(reachable)
        self.open_btn.setEnabled(reachable)

        editable = not is_running and not self._busy
        self.edit_btn.setEnabled(editable)
        self.edit_btn.setToolTip("Edit tunnel" if editable else "Stop the tunnel to edit it")
        
        # Opacity for card
        offline = "false" if is_running else "true"
        if self.status_card.property("offline") != offline:
            self.status_card.setProperty("offline", offline)
            self.status_card.style().unpolish(self.status_card)
            self.status_card.style().polish(self.status_card)

    def update_logs(self):
        if not self.current_tunnel_name: return
        logs = self.tunnel_manager.get_logs_by_name(self.current_tunnel_name)
        if logs == self._shown_logs:
            return
        self._shown_logs = logs
        # Follow new output only if the reader is at the bottom; otherwise keep their place
        bar = self.log_display.verticalScrollBar()
        follow = bar.value() >= bar.maximum() - 4
        position = bar.value()
        self.log_display.setPlainText(logs)
        bar.setValue(bar.maximum() if follow else position)

    def handle_toggle(self):
        self.toggle_requested.emit(self.current_tunnel_name)
        # Optimistic update or wait for refresh? Wait for refresh loop handled by main window usually.
        # But for UX response:
        QTimer.singleShot(200, self.refresh_state)

    def set_busy(self, busy, text=None):
        """Lock Turn ON/Stop, Edit and Delete while a start/stop runs in the background."""
        self._busy = busy
        self.toggle_btn.setEnabled(not busy)
        self.delete_btn.setEnabled(not busy)
        if busy:
            self.edit_btn.setEnabled(False)
        if text:
            self.toggle_btn.setText(text)

    def copy_link(self):
        if self._public_url:
            QApplication.clipboard().setText(self._public_url)
            self.copy_symbol.setText("✓")
            QTimer.singleShot(1500, lambda: self.copy_symbol.setText("⎙"))

    def open_url(self):
        if self._public_url:
            QDesktopServices.openUrl(QUrl(self._public_url))

    def show_qr(self):
        if self._public_url:
             from ..dialogs.qr_code import QRCodeDialog
             dialog = QRCodeDialog(self._public_url, self.window())
             dialog.exec()
    
    def stop(self):
        self.log_timer.stop()
