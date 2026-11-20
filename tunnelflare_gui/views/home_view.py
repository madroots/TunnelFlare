from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from ..components.tunnel_row import TunnelRow

from ..resources import RESOURCE_DIR

# The page has 24 px side margins. On the right, the scrollbar lives in the outer
# part of that margin, so cards stay aligned with the header when the list scrolls.
PAGE_MARGIN = 24
SCROLLBAR_EDGE_GAP = 8
CONTENT_INSET = PAGE_MARGIN - SCROLLBAR_EDGE_GAP


class HomeView(QWidget):
    add_requested = Signal()
    tunnel_clicked = Signal(str) # name
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
        # Standardized Margin: Top 28, Side 24, Bottom 40
        layout.setContentsMargins(PAGE_MARGIN, 28, SCROLLBAR_EDGE_GAP, 40)
        layout.setSpacing(0)
        
        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, CONTENT_INSET, 0)
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
        add_btn.setToolTip("Add a tunnel")
        add_btn.setAccessibleName("Add tunnel")
        
        add_btn.setIcon(QIcon(str(RESOURCE_DIR / "add.svg")))
        add_btn.setIconSize(QSize(30, 30))
        
        add_btn.clicked.connect(self.add_requested.emit)
        
        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(add_btn)
        layout.addLayout(header)

        # Update banner (hidden until a newer release is found)
        self.update_banner = QFrame()
        self.update_banner.setObjectName("UpdateBanner")
        banner_layout = QHBoxLayout(self.update_banner)
        banner_layout.setContentsMargins(14, 10, 8, 10)
        banner_layout.setSpacing(10)
        self.update_label = QLabel()
        self.update_label.setObjectName("UpdateText")
        update_btn = QPushButton("Update")
        update_btn.setObjectName("BannerAction")
        update_btn.setCursor(Qt.PointingHandCursor)
        update_btn.clicked.connect(self.update_requested.emit)
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setObjectName("BannerClose")
        dismiss_btn.setCursor(Qt.PointingHandCursor)
        dismiss_btn.setToolTip("Remind me later")
        dismiss_btn.clicked.connect(self._dismiss_update)
        banner_layout.addWidget(self.update_label, 1)
        banner_layout.addWidget(update_btn)
        banner_layout.addWidget(dismiss_btn)
        # The banner brings its own top spacing, so hiding it leaves no gap
        self.banner_container = QWidget()
        banner_row = QHBoxLayout(self.banner_container)
        banner_row.setContentsMargins(0, 18, CONTENT_INSET, 0)
        banner_row.addWidget(self.update_banner)
        layout.addWidget(self.banner_container)
        self.banner_container.hide()
        
        layout.addSpacing(26)
        
        # List Container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)
        self.container_layout.setSpacing(26) # Matching .card margin-top
        self.container_layout.setContentsMargins(0, 0, CONTENT_INSET, 0)

        self.empty_label = QLabel("No tunnels yet.\nClick + to add one.")
        self.empty_label.setObjectName("Subtitle")
        self.container_layout.addWidget(self.empty_label)
        
        self.scroll_area.setWidget(self.container)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(self._fit_scrollbar_gutter)
        layout.addWidget(self.scroll_area)

    def _fit_scrollbar_gutter(self, minimum, maximum):
        # A visible scrollbar takes its width from the viewport; give that width
        # back on the right so the cards keep their size and alignment.
        bar = self.scroll_area.verticalScrollBar()
        bar_width = bar.sizeHint().width() if maximum > minimum else 0
        self.container_layout.setContentsMargins(0, 0, max(0, CONTENT_INSET - bar_width), 0)

    def show_update(self, version):
        self.update_label.setText(f"TunnelFlare {version} is available.")
        self.banner_container.show()

    def hide_update(self):
        self.banner_container.hide()

    def _dismiss_update(self):
        self.hide_update()
        self.update_dismissed.emit()

    def refresh(self, active_tunnels=None):
        """Sync the cards with the saved tunnels, updating existing cards in place."""
        if active_tunnels is None:
            active_tunnels = self.tunnel_manager.get_active_tunnels()
        running = {t['name']: t for t in active_tunnels}
        configs = self.config_manager.get_tunnels()
        names = [config['name'] for config in configs]

        for name in [name for name in self.rows if name not in names]:
            row = self.rows.pop(name)
            self.container_layout.removeWidget(row)
            row.deleteLater()

        for index, config in enumerate(configs):
            row = self.rows.get(config['name'])
            if row is None:
                row = TunnelRow(config, running.get(config['name']))
                row.clicked.connect(self.tunnel_clicked.emit)
                self.rows[config['name']] = row
            else:
                row.set_data(config, running.get(config['name']))
            if self.container_layout.indexOf(row) != index:
                self.container_layout.removeWidget(row)
                self.container_layout.insertWidget(index, row)

        self.empty_label.setVisible(not configs)
