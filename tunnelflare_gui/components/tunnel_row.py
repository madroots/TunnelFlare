import math

from PySide6.QtCore import QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QWidget

from ..icons import tinted_pixmap
from ..styles import Styles
from .elided_label import ElidedLabel
from .toggle_switch import ToggleSwitch

THEME = Styles.THEME
DOT_COLORS = {"online": THEME["online"], "starting": THEME["starting"], "stopped": THEME["offline"]}


def status_style(tunnel_info):
    """(label, dot state, label style) for a get_active_tunnels() entry; None = stopped."""
    if not tunnel_info:
        return "Stopped", "stopped", "StatusStopped"
    if tunnel_info.get("status") == "Running":
        return "Online", "online", "StatusOnline"
    if tunnel_info.get("status") == "Reconnecting":
        return "Reconnecting…", "starting", "StatusStarting"
    return "Starting…", "starting", "StatusStarting"


def restyle(widget, object_name):
    """Switch a widget to another stylesheet selector, repolishing only on change."""
    if widget.objectName() != object_name:
        widget.setObjectName(object_name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def set_text(label, text):
    if label.text() != text:
        label.setText(text)


def set_flag(widget, name, value):
    """Set a boolean stylesheet property, repolishing only on change."""
    if bool(widget.property(name)) != value:
        widget.setProperty(name, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class StatusDot(QWidget):
    """Status light: green with a soft halo when online, a pulsing amber halo while
    connecting, plain grey when stopped."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.state = "stopped"
        self._phase = 0.0
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(1400)
        self._pulse.setLoopCount(-1)
        self._pulse.valueChanged.connect(self._on_pulse)

    def set_state(self, state):
        if state == self.state:
            return
        self.state = state
        if state == "starting":
            self._pulse.start()
        else:
            self._pulse.stop()
        self.update()

    def _on_pulse(self, value):
        self._phase = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        color = QColor(DOT_COLORS[self.state])
        center = QRectF(self.rect()).center()
        if self.state != "stopped":
            halo = QColor(color)
            if self.state == "starting":
                halo.setAlphaF(0.12 + 0.28 * math.sin(math.pi * self._phase))
            else:
                halo.setAlphaF(0.22)
            painter.setBrush(halo)
            painter.drawEllipse(center, 8, 8)
        painter.setBrush(color)
        painter.drawEllipse(center, 4, 4)


class LinkPill(QFrame):
    """A tunnel's public URL with a copy icon; clicking anywhere on it copies the link."""

    copy_requested = Signal()

    def __init__(self, object_name="LinkPill", text_style="LinkText", parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(8)
        self.text = ElidedLabel()
        self.text.setObjectName(text_style)
        self.icon = QLabel()
        self.icon.setPixmap(tinted_pixmap("copy.svg", THEME["text_sub"], 14))
        layout.addWidget(self.text, 1)
        layout.addWidget(self.icon)

    def set_url(self, url):
        # The scheme adds nothing here; dropping it leaves room for the name
        set_text(self.text, url.removeprefix("https://"))
        self.setToolTip(f"Copy {url}")

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.copy_requested.emit()
        event.accept()


class TunnelRow(QFrame):
    """A tunnel on the home screen: status, local address, public link and an on/off
    switch. Clicking the card (or Enter/Space) opens its details."""

    clicked = Signal(str)  # tunnel name
    toggle_requested = Signal(str)  # tunnel name
    notify = Signal(str)  # short confirmation for a toast

    def __init__(self, config, tunnel_info=None, busy=None, parent=None):
        super().__init__(parent)
        self.setObjectName("TunnelCard")
        self.setAttribute(Qt.WA_Hover)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.name = None
        self.url = None
        self.setup_ui()
        self.set_data(config, tunnel_info, busy)

    def setup_ui(self):
        grid = QGridLayout(self)
        grid.setContentsMargins(14, 14, 16, 14)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(1, 1)

        self.dot = StatusDot()
        self.name_label = QLabel()
        self.name_label.setObjectName("CardTitle")
        self.switch = ToggleSwitch()
        self.switch.clicked.connect(lambda: self.toggle_requested.emit(self.name))

        meta = QHBoxLayout()
        meta.setSpacing(6)
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
        for widget in (self.status_label, separator, self.address_label, self.https_chip, self.host_chip):
            meta.addWidget(widget)
        meta.addStretch()

        self.link = LinkPill()
        self.link.copy_requested.connect(self.copy_link)

        grid.addWidget(self.dot, 0, 0, Qt.AlignVCenter)
        grid.addWidget(self.name_label, 0, 1)
        grid.addWidget(self.switch, 0, 2, Qt.AlignVCenter)
        grid.addLayout(meta, 1, 1, 1, 2)
        grid.addWidget(self.link, 2, 1, 1, 2)
        grid.setRowMinimumHeight(2, 0)

    def set_data(self, config, tunnel_info=None, busy=None):
        """Show `config` with its runtime state (`tunnel_info` is None when stopped).
        `busy` is "Starting…" / "Stopping…" while a start or stop is in progress."""
        self.name = config["name"]
        label, dot_state, style = status_style(tunnel_info)
        if busy:
            label, dot_state, style = busy, "starting", "StatusStarting"
        set_text(self.name_label, self.name)
        set_text(self.status_label, label)
        restyle(self.status_label, style)
        self.dot.set_state(dot_state)
        set_text(self.address_label, f"localhost:{config['port']}")
        self.https_chip.setVisible(config.get("protocol") == "https")
        self.host_chip.setVisible(bool(config.get("rewrite_host")))

        self.url = tunnel_info.get("public_url") if tunnel_info else None
        if self.url:
            self.link.set_url(self.url)
        self.link.setVisible(bool(self.url))

        self.switch.set_on(busy == "Starting…" if busy else bool(tunnel_info))
        self.switch.setEnabled(not busy)
        self.switch.setToolTip("Stop tunnel" if tunnel_info else "Start tunnel")
        self.setAccessibleName(f"{self.name}, localhost:{config['port']}, {label.rstrip('…').lower()}")

    def copy_link(self):
        if self.url:
            QApplication.clipboard().setText(self.url)
            self.notify.emit("Link copied")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.name)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit(self.name)
        else:
            super().keyPressEvent(event)
