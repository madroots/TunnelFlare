from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Property
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QAbstractButton

from ..styles import Styles

TRACK_OFF = QColor("#3a3a3c")
TRACK_ON = QColor(Styles.THEME["accent"])
KNOB = QColor("#ffffff")


class ToggleSwitch(QAbstractButton):
    """On/off switch with a sliding knob. Users toggle it with a click or Space."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.TabFocus)
        self._position = 0.0  # 0 = off, 1 = on; animated between the two
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._slide)

    def sizeHint(self):
        return QSize(44, 26)

    def set_on(self, on):
        """Show a state that came from outside (no signal, no animation)."""
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        self._animation.stop()
        self._position = 1.0 if on else 0.0
        self.update()

    def _slide(self, on):
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if on else 0.0)
        self._animation.start()

    def _get_position(self):
        return self._position

    def _set_position(self, value):
        self._position = value
        self.update()

    position = Property(float, _get_position, _set_position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.45)
        track = QRectF(1, 2, 42, 22)
        t = self._position
        color = QColor(
            int(TRACK_OFF.red() + (TRACK_ON.red() - TRACK_OFF.red()) * t),
            int(TRACK_OFF.green() + (TRACK_ON.green() - TRACK_OFF.green()) * t),
            int(TRACK_OFF.blue() + (TRACK_ON.blue() - TRACK_OFF.blue()) * t),
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(track, 11, 11)
        knob = QRectF(track.left() + 3 + t * (track.width() - 24), track.top() + 3, 16, 16)
        painter.setBrush(KNOB)
        painter.drawEllipse(knob)
        if self.property("focusVisible"):
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QColor(255, 138, 0, 180))
            painter.drawRoundedRect(track.adjusted(-1, -1, 1, 1), 12, 12)
