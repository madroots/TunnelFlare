"""Theme-coloured icons: monochrome SVGs are tinted at runtime, so one file serves
every state and nothing depends on a font having a symbol glyph."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from .resources import RESOURCE_DIR

RENDER_SCALE = 3.0  # device pixels per point; crisp on every common screen


def tinted_pixmap(name, color, size):
    """The SVG `name` as a `size`-point pixmap, every opaque pixel set to `color`."""
    source = QIcon(str(RESOURCE_DIR / name)).pixmap(QSize(size, size), RENDER_SCALE)
    pixmap = QPixmap(source.size())
    pixmap.setDevicePixelRatio(source.devicePixelRatio())
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.drawPixmap(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(0, 0, size, size, QColor(color))
    painter.end()
    return pixmap


def tinted_icon(name, color, size=20, disabled_color="#4a4a4c", hover_color=None):
    icon = QIcon()
    icon.addPixmap(tinted_pixmap(name, color, size), QIcon.Normal)
    icon.addPixmap(tinted_pixmap(name, hover_color or color, size), QIcon.Active)
    icon.addPixmap(tinted_pixmap(name, disabled_color, size), QIcon.Disabled)
    return icon
