"""Application bootstrap shared by the GUI, the packaged-app self-test and the tests.

Everything that could make the app look different per OS is pinned here: the
Fusion style, a fixed dark palette (ignores the OS light/dark setting), and the
bundled Inter / JetBrains Mono fonts at a fixed pixel size.
"""
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from tunnelflare_backend import __version__
from .resources import RESOURCE_DIR
from .styles import Styles

UI_FONT_FAMILY = "Inter"
MONO_FONT_FAMILY = "JetBrains Mono"
UI_FONT_PIXEL_SIZE = 13


def load_fonts():
    """Register the bundled fonts and return the font families that loaded."""
    families = set()
    for path in sorted((RESOURCE_DIR / "fonts").glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id != -1:
            families.update(QFontDatabase.applicationFontFamilies(font_id))
    return families


def dark_palette():
    theme = Styles.THEME
    palette = QPalette()
    colors = {
        QPalette.Window: theme["bg"],
        QPalette.WindowText: theme["text_main"],
        QPalette.Base: "#1a1a1a",
        QPalette.AlternateBase: theme["card"],
        QPalette.Text: theme["text_main"],
        QPalette.PlaceholderText: theme["port"],
        QPalette.Button: theme["card"],
        QPalette.ButtonText: theme["text_main"],
        QPalette.BrightText: theme["text_main"],
        QPalette.Highlight: theme["accent"],
        QPalette.HighlightedText: theme["text_main"],
        QPalette.Link: theme["accent"],
        QPalette.ToolTipBase: theme["card"],
        QPalette.ToolTipText: theme["text_main"],
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#777777"))
    return palette


def create_application(argv):
    app = QApplication.instance() or QApplication(argv)
    QCoreApplication.setApplicationName("TunnelFlare")
    QCoreApplication.setApplicationVersion(__version__)
    # TunnelFlare keeps running in the tray and quits explicitly; closing the last
    # visible dialog while the window is hidden must not end the app.
    app.setQuitOnLastWindowClosed(False)
    if app.setStyle("Fusion") is None:
        raise RuntimeError("Qt's Fusion style is unavailable")
    load_fonts()
    font = QFont(UI_FONT_FAMILY)
    font.setPixelSize(UI_FONT_PIXEL_SIZE)
    app.setFont(font)
    app.setPalette(dark_palette())
    app.setStyleSheet(Styles.STYLESHEET)
    app.setWindowIcon(QIcon(str(RESOURCE_DIR / "tray.svg")))
    return app
