from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy


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
