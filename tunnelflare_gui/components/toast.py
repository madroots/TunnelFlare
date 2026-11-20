from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

VISIBLE_MS = 1600
BOTTOM_GAP = 28


class Toast(QLabel):
    """A short confirmation ("Link copied") that fades in near the bottom of its window."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(160)
        self._fade.finished.connect(self._after_fade)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._fade_to(0.0))
        self.hide()

    def show_message(self, text):
        self.setText(text)
        self.adjustSize()
        self.reposition()
        self.raise_()
        self.show()
        self._fade_to(1.0)
        self._timer.start(VISIBLE_MS)

    def reposition(self):
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - BOTTOM_GAP)

    def _fade_to(self, opacity):
        self._fade.stop()
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(opacity)
        self._fade.start()

    def _after_fade(self):
        if self._opacity.opacity() == 0.0:
            self.hide()
