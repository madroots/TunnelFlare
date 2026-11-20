from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QWidget

KEYBOARD_REASONS = (Qt.TabFocusReason, Qt.BacktabFocusReason, Qt.ShortcutFocusReason)


class KeyboardFocusMarker(QObject):
    """Sets the focusVisible property on a widget while it has focus that came from
    the keyboard, so the stylesheet draws focus rings for keyboard users only (like
    CSS :focus-visible). Clicking a card or button never leaves a ring behind."""

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind in (QEvent.FocusIn, QEvent.FocusOut) and isinstance(watched, QWidget):
            visible = kind == QEvent.FocusIn and event.reason() in KEYBOARD_REASONS
            if bool(watched.property("focusVisible")) != visible:
                watched.setProperty("focusVisible", visible)
                watched.style().unpolish(watched)
                watched.style().polish(watched)
                watched.update()
        return False
