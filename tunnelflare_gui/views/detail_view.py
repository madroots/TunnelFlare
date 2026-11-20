from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

from ..components.elided_label import ElidedLabel
from ..components.tunnel_row import StatusDot, restyle, set_flag, set_text, status_style
from ..dialogs import message_dialog
from ..icons import tinted_icon, tinted_pixmap
from ..styles import Styles

THEME = Styles.THEME
# Statuses in which the public URL has been reachable at least once
REACHABLE = ("Running", "Reconnecting")


class LinkPanel(QFrame):
    """The public link; clicking it copies the link once there is one."""

    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class DetailView(QWidget):
    back_requested = Signal()
    toggle_requested = Signal(str)  # tunnel name
    edit_requested = Signal(str)  # tunnel name
    notify = Signal(str)  # toast message

    def __init__(self, tunnel_manager, parent=None):
        super().__init__(parent)
        self.tunnel_manager = tunnel_manager
        self.current_tunnel_name = None
        self._busy = False
        self._busy_text = None
        self._shown_logs = None
        self._public_url = None
        self.setup_ui()
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.update_logs)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(4)
        self.back_btn = QPushButton("Tunnels")
        self.back_btn.setObjectName("GhostButton")
        self.back_btn.setIcon(tinted_icon("back.svg", THEME["accent"], 16, hover_color=THEME["accent_hover"]))
        self.back_btn.setIconSize(QSize(16, 16))
        self.back_btn.setCursor(Qt.PointingHandCursor)
        self.back_btn.setToolTip("Back to all tunnels")
        self.back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(self.back_btn)
        header.addStretch()
        self.edit_btn = self._icon_button("edit.svg", THEME["text_main"], "Edit tunnel")
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.current_tunnel_name))
        self.delete_btn = self._icon_button("delete.svg", THEME["danger"], "Delete tunnel")
        self.delete_btn.setToolTip("Delete tunnel")
        self.delete_btn.clicked.connect(self.handle_delete)
        header.addWidget(self.edit_btn)
        header.addWidget(self.delete_btn)
        layout.addLayout(header)
        layout.addSpacing(14)

        self.name_label = ElidedLabel()
        self.name_label.setObjectName("DetailTitle")
        layout.addWidget(self.name_label)
        layout.addSpacing(6)
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.dot = StatusDot()
        self.status_label = QLabel()
        self.status_label.setObjectName("StatusStopped")
        separator = QLabel("·")
        separator.setObjectName("MetaText")
        self.address_label = QLabel()
        self.address_label.setObjectName("MetaText")
        self.https_chip = QLabel("HTTPS")
        self.https_chip.setObjectName("Chip")
        self.host_chip = QLabel("HOST")
        self.host_chip.setObjectName("Chip")
        self.host_chip.setToolTip("Requests are sent as “localhost”")
        for widget in (self.dot, self.status_label, separator, self.address_label, self.https_chip, self.host_chip):
            status_row.addWidget(widget)
        status_row.addStretch()
        layout.addLayout(status_row)
        layout.addSpacing(18)

        self.link_panel = LinkPanel()
        self.link_panel.setObjectName("LinkPanel")
        self.link_panel.setAttribute(Qt.WA_Hover)
        self.link_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.link_panel.clicked.connect(self.copy_link)
        panel = QVBoxLayout(self.link_panel)
        panel.setContentsMargins(14, 11, 12, 12)
        panel.setSpacing(6)
        panel.addWidget(QLabel("PUBLIC LINK", objectName="SectionLabel"))
        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        self.url_text = ElidedLabel()
        self.url_text.setObjectName("LinkTextLarge")
        self.url_placeholder = QLabel()
        self.url_placeholder.setObjectName("LinkPlaceholder")
        self.copy_icon = QLabel()
        self.copy_icon.setPixmap(tinted_pixmap("copy.svg", THEME["text_sub"], 16))
        link_row.addWidget(self.url_text, 1)
        link_row.addWidget(self.url_placeholder, 1)
        link_row.addWidget(self.copy_icon)
        panel.addLayout(link_row)
        layout.addWidget(self.link_panel)
        layout.addSpacing(12)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.open_btn = self._action_button("Open in Browser", "open.svg", self.open_url)
        self.qr_btn = self._action_button("QR Code", "qr.svg", self.show_qr)
        actions.addWidget(self.open_btn, 1)
        actions.addWidget(self.qr_btn, 1)
        layout.addLayout(actions)
        layout.addSpacing(12)

        self.toggle_btn = QPushButton("Start Tunnel")
        self.toggle_btn.setObjectName("PrimaryAction")
        self.toggle_btn.setMinimumHeight(50)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.handle_toggle)
        layout.addWidget(self.toggle_btn)
        layout.addSpacing(22)

        logs_header = QHBoxLayout()
        logs_header.addWidget(QLabel("LOGS", objectName="SectionLabel"))
        logs_header.addStretch()
        self.copy_logs_btn = QPushButton("Copy")
        self.copy_logs_btn.setObjectName("SmallGhostButton")
        self.copy_logs_btn.setCursor(Qt.PointingHandCursor)
        self.copy_logs_btn.setToolTip("Copy all logs")
        self.copy_logs_btn.clicked.connect(self.copy_logs)
        logs_header.addWidget(self.copy_logs_btn)
        layout.addLayout(logs_header)
        layout.addSpacing(6)
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("Logs appear here when the tunnel starts.")
        layout.addWidget(self.log_display, 1)

    @staticmethod
    def _icon_button(svg, hover_color, name):
        button = QPushButton()
        button.setObjectName("IconButton")
        button.setFixedSize(34, 34)
        button.setIcon(tinted_icon(svg, THEME["text_sub"], 18, hover_color=hover_color))
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.PointingHandCursor)
        button.setAccessibleName(name)
        return button

    @staticmethod
    def _action_button(text, svg, slot):
        button = QPushButton(f" {text}")  # a little air between icon and label
        button.setAccessibleName(text)
        button.setIcon(tinted_icon(svg, THEME["text_main"], 18))
        button.setIconSize(QSize(18, 18))
        button.setMinimumHeight(44)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def handle_delete(self):
        if self._busy:
            return
        name = self.current_tunnel_name
        if not message_dialog.confirm(
            self.window(), f"Delete “{name}”?",
            "The tunnel stops and its settings are removed. This can’t be undone.",
            "Delete", destructive=True, icon="danger",
        ):
            return
        tunnel_id = next((t['id'] for t in self.tunnel_manager.get_active_tunnels() if t['name'] == name), None)
        if tunnel_id:
            self.tunnel_manager.stop_tunnel(tunnel_id)
        self.tunnel_manager.config_manager.remove_tunnel(name)
        self.back_requested.emit()

    def load_tunnel(self, name):
        self.current_tunnel_name = name
        self.name_label.setText(name)
        self.name_label.setToolTip(name)
        config = self.tunnel_manager.config_manager.get_tunnel(name) or {}
        self.address_label.setText(f"localhost:{config.get('port', '')}")
        self.https_chip.setVisible(config.get("protocol") == "https")
        self.host_chip.setVisible(bool(config.get("rewrite_host")))
        self._shown_logs = None
        self.log_display.clear()
        self.refresh_state()
        self.update_logs()
        self.log_timer.start(1000)

    def refresh_state(self, active_tunnels=None):
        if not self.current_tunnel_name:
            return
        if active_tunnels is None:
            active_tunnels = self.tunnel_manager.get_active_tunnels()
        info = next((t for t in active_tunnels if t['name'] == self.current_tunnel_name), None)
        running = bool(info)
        self._public_url = info.get('public_url') if info else None
        reachable = bool(self._public_url) and info.get('status') in REACHABLE

        label, dot_state, style = status_style(info)
        if self._busy_text:
            label, dot_state, style = self._busy_text, "starting", "StatusStarting"
        set_text(self.status_label, label)
        restyle(self.status_label, style)
        self.dot.set_state(dot_state)

        if self._public_url:
            self.url_text.setText(self._public_url.removeprefix("https://"))
            self.link_panel.setToolTip(f"Copy {self._public_url}")
        else:
            set_text(self.url_placeholder, "Requesting a link from Cloudflare…" if running
                     else "Start the tunnel to get a public link.")
            self.link_panel.setToolTip("")
        has_url = bool(self._public_url)
        self.url_text.setVisible(has_url)
        self.copy_icon.setVisible(has_url)
        self.url_placeholder.setVisible(not has_url)
        set_flag(self.link_panel, "copyable", has_url)
        self.link_panel.setCursor(Qt.PointingHandCursor if has_url else Qt.ArrowCursor)
        # The link only works once cloudflared has connected to Cloudflare
        self.open_btn.setEnabled(reachable)
        self.qr_btn.setEnabled(reachable)

        if not self._busy:
            set_text(self.toggle_btn, "Stop Tunnel" if running else "Start Tunnel")
            restyle(self.toggle_btn, "DestructiveButton" if running else "PrimaryAction")
        editable = not running and not self._busy
        self.edit_btn.setEnabled(editable)
        self.edit_btn.setToolTip("Edit tunnel" if editable else "Stop the tunnel to edit it")

    def update_logs(self):
        if not self.current_tunnel_name:
            return
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
        self.copy_logs_btn.setEnabled(bool(logs.strip()))

    def handle_toggle(self):
        self.toggle_requested.emit(self.current_tunnel_name)

    def set_busy(self, busy, text=None):
        """Lock Start/Stop, Edit and Delete while a start/stop runs in the background."""
        self._busy = busy
        self._busy_text = text if busy else None
        self.toggle_btn.setEnabled(not busy)
        self.delete_btn.setEnabled(not busy)
        if busy:
            self.edit_btn.setEnabled(False)
        if text:
            self.toggle_btn.setText(text)
        self.refresh_state()

    def copy_link(self):
        if self._public_url:
            QApplication.clipboard().setText(self._public_url)
            self.notify.emit("Link copied")

    def copy_logs(self):
        QApplication.clipboard().setText(self.log_display.toPlainText())
        self.notify.emit("Logs copied")

    def open_url(self):
        if self._public_url:
            QDesktopServices.openUrl(QUrl(self._public_url))

    def show_qr(self):
        if self._public_url:
            from ..dialogs.qr_code import QRCodeDialog
            QRCodeDialog(self._public_url, self.window()).exec()

    def stop(self):
        self.log_timer.stop()
