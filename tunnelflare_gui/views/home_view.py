from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..components.tunnel_row import TunnelRow, set_text
from ..icons import tinted_icon, tinted_pixmap
from ..resources import RESOURCE_DIR
from ..styles import Styles

THEME = Styles.THEME
# The page has 24 px side margins. On the right, the scrollbar lives in the outer
# part of that margin, so cards stay aligned with the header when the list scrolls.
PAGE_MARGIN = 24
SCROLLBAR_EDGE_GAP = 8
CONTENT_INSET = PAGE_MARGIN - SCROLLBAR_EDGE_GAP


def summary(total, online):
    if not total:
        return "Share local apps with a secure public link"
    return f"{online} of {total} online"


class HomeView(QWidget):
    add_requested = Signal()
    tunnel_clicked = Signal(str)  # name
    toggle_requested = Signal(str)  # name
    notify = Signal(str)  # toast message
    update_requested = Signal()
    update_dismissed = Signal()

    def __init__(self, config_manager, tunnel_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.tunnel_manager = tunnel_manager
        self.rows = {}  # tunnel name -> TunnelRow, updated in place on every refresh
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, 26, SCROLLBAR_EDGE_GAP, 24)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, CONTENT_INSET, 0)
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("TunnelFlare")
        title.setObjectName("AppTitle")
        self.subtitle = QLabel(summary(0, 0))
        self.subtitle.setObjectName("AppSubtitle")
        header_text.addWidget(title)
        header_text.addWidget(self.subtitle)

        self.add_btn = QPushButton()
        self.add_btn.setObjectName("AddButton")
        self.add_btn.setFixedSize(40, 40)
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.setToolTip("Add a tunnel")
        self.add_btn.setAccessibleName("Add tunnel")
        self.add_btn.setIcon(QIcon(str(RESOURCE_DIR / "add.svg")))
        self.add_btn.setIconSize(QSize(22, 22))
        self.add_btn.clicked.connect(self.add_requested.emit)
        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        # Update banner (hidden until a newer release is found)
        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        banner_layout = QHBoxLayout(self.update_banner)
        banner_layout.setContentsMargins(12, 7, 6, 7)
        banner_layout.setSpacing(10)
        banner_icon = QLabel()
        banner_icon.setPixmap(tinted_pixmap("update.svg", THEME["accent"], 18))
        self.update_label = QLabel()
        self.update_label.setObjectName("UpdateText")
        update_btn = QPushButton("Update")
        update_btn.setObjectName("BannerAction")
        update_btn.setCursor(Qt.PointingHandCursor)
        update_btn.clicked.connect(self.update_requested.emit)
        dismiss_btn = QPushButton()
        dismiss_btn.setObjectName("IconButton")
        dismiss_btn.setFixedSize(34, 34)
        dismiss_btn.setIcon(tinted_icon("close.svg", THEME["text_sub"], 18, hover_color=THEME["text_main"]))
        dismiss_btn.setIconSize(QSize(18, 18))
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.setToolTip("Remind me later")
        dismiss_btn.setAccessibleName("Dismiss update")
        dismiss_btn.clicked.connect(self._dismiss_update)
        banner_layout.addWidget(banner_icon)
        banner_layout.addWidget(self.update_label, 1)
        banner_layout.addWidget(update_btn)
        banner_layout.addWidget(dismiss_btn)
        # The banner brings its own top spacing, so hiding it leaves no gap
        self.banner_container = QWidget()
        banner_row = QHBoxLayout(self.banner_container)
        banner_row.setContentsMargins(0, 16, CONTENT_INSET, 0)
        banner_row.addWidget(self.update_banner)
        layout.addWidget(self.banner_container)
        self.banner_container.hide()

        layout.addSpacing(20)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)
        self.container_layout.setSpacing(12)
        self.container_layout.setContentsMargins(0, 0, CONTENT_INSET, 0)
        self.scroll_area.setWidget(self.container)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(self._fit_scrollbar_gutter)
        layout.addWidget(self.scroll_area, 1)

        self.empty_state = self._build_empty_state()
        layout.addWidget(self.empty_state, 1)

    def _build_empty_state(self):
        empty = QWidget()
        column = QVBoxLayout(empty)
        column.setContentsMargins(16, 0, CONTENT_INSET + 16, 48)
        column.setSpacing(0)
        column.addStretch()
        art = QLabel()
        art.setPixmap(QIcon(str(RESOURCE_DIR / "tray.svg")).pixmap(QSize(64, 64)))
        art.setAlignment(Qt.AlignCenter)
        column.addWidget(art)
        column.addSpacing(18)
        title = QLabel("No tunnels yet")
        title.setObjectName("EmptyTitle")
        title.setAlignment(Qt.AlignCenter)
        column.addWidget(title)
        column.addSpacing(6)
        text = QLabel("Give a local app a public HTTPS link in seconds. No Cloudflare account needed.")
        text.setObjectName("EmptyText")
        text.setAlignment(Qt.AlignCenter)
        text.setWordWrap(True)
        column.addWidget(text)
        column.addSpacing(22)
        self.empty_add_btn = QPushButton("Add Tunnel")
        self.empty_add_btn.setObjectName("PrimaryAction")
        self.empty_add_btn.setFixedSize(180, 44)
        self.empty_add_btn.setCursor(Qt.PointingHandCursor)
        self.empty_add_btn.clicked.connect(self.add_requested.emit)
        column.addWidget(self.empty_add_btn, 0, Qt.AlignHCenter)
        column.addStretch()
        return empty

    def _fit_scrollbar_gutter(self, minimum, maximum):
        # A visible scrollbar takes its width from the viewport; give that width
        # back on the right so the cards keep their size and alignment.
        bar = self.scroll_area.verticalScrollBar()
        bar_width = bar.sizeHint().width() if maximum > minimum else 0
        self.container_layout.setContentsMargins(0, 0, max(0, CONTENT_INSET - bar_width), 0)

    def show_update(self, version):
        self.update_label.setText(f"TunnelFlare {version} is available")
        self.banner_container.show()

    def hide_update(self):
        self.banner_container.hide()

    def _dismiss_update(self):
        self.hide_update()
        self.update_dismissed.emit()

    def refresh(self, active_tunnels=None, busy=None):
        """Sync the cards with the saved tunnels, updating existing cards in place.
        `busy` maps tunnel names to "Starting…" / "Stopping…" while workers run."""
        if active_tunnels is None:
            active_tunnels = self.tunnel_manager.get_active_tunnels()
        busy = busy or {}
        running = {t['name']: t for t in active_tunnels}
        configs = self.config_manager.get_tunnels()
        names = [config['name'] for config in configs]

        for name in [name for name in self.rows if name not in names]:
            row = self.rows.pop(name)
            self.container_layout.removeWidget(row)
            row.deleteLater()

        for index, config in enumerate(configs):
            name = config['name']
            row = self.rows.get(name)
            if row is None:
                row = TunnelRow(config, running.get(name), busy.get(name))
                row.clicked.connect(self.tunnel_clicked.emit)
                row.toggle_requested.connect(self.toggle_requested.emit)
                row.notify.connect(self.notify.emit)
                self.rows[name] = row
            else:
                row.set_data(config, running.get(name), busy.get(name))
            if self.container_layout.indexOf(row) != index:
                self.container_layout.removeWidget(row)
                self.container_layout.insertWidget(index, row)

        online = sum(1 for name in names if running.get(name, {}).get('status') == 'Running')
        set_text(self.subtitle, summary(len(configs), online))
        self.scroll_area.setVisible(bool(configs))
        self.empty_state.setVisible(not configs)
