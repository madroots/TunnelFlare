"""App-styled dialogs that replace QMessageBox: same look on every OS."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from ..icons import tinted_pixmap
from ..styles import Styles

THEME = Styles.THEME
# icon kind -> (svg, colour)
ICONS = {
    "warning": ("alert.svg", THEME["starting"]),
    "error": ("alert.svg", THEME["danger"]),
    "danger": ("delete.svg", THEME["danger"]),
    "update": ("update.svg", THEME["accent"]),
    "info": ("alert.svg", THEME["accent"]),
    "success": ("check.svg", THEME["online"]),
}
BUTTON_STYLES = {"primary": "PrimaryAction", "destructive": "DestructiveButton", "secondary": ""}


def fit_to_content(dialog):
    """Give a fixed-width dialog the height its wrapped text needs. Qt sizes windows
    from width-independent hints, which squeezes word-wrapped labels."""
    dialog.ensurePolished()
    dialog.setFixedHeight(dialog.heightForWidth(dialog.width()))


class MessageDialog(QDialog):
    """Icon, title, message and buttons. `buttons` is a list of (text, style) with
    style "primary", "destructive" or "secondary"; `choice` holds the clicked index,
    or None when the dialog was dismissed."""

    def __init__(self, parent, title, message, buttons, icon=None):
        super().__init__(parent)
        self.setObjectName("MessageDialog")
        self.setWindowTitle("TunnelFlare")
        self.setFixedWidth(400)
        self.choice = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 24)
        layout.setSpacing(0)
        if icon:
            svg, color = ICONS[icon]
            badge = QLabel()
            badge.setObjectName(f"IconBadge_{icon}")
            badge.setFixedSize(44, 44)
            badge.setAlignment(Qt.AlignCenter)
            badge.setPixmap(tinted_pixmap(svg, color, 22))
            layout.addWidget(badge)
            layout.addSpacing(16)
        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        layout.addSpacing(8)
        body = QLabel(message)
        body.setObjectName("DialogText")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(body)
        layout.addSpacing(24)

        stacked = len(buttons) > 2
        row = QVBoxLayout() if stacked else QHBoxLayout()
        row.setSpacing(10)
        widgets = []
        for index, (text, style) in enumerate(buttons):
            button = QPushButton(text)
            if BUTTON_STYLES[style]:
                button.setObjectName(BUTTON_STYLES[style])
            button.setMinimumHeight(44)
            button.setCursor(Qt.PointingHandCursor)
            button.setAutoDefault(False)
            button.clicked.connect(lambda checked=False, i=index: self._choose(i))
            widgets.append(button)
        # Side by side: secondary buttons on the left; stacked: main action on top
        order = widgets if stacked else sorted(widgets, key=lambda b: b.objectName() != "")
        for button in order:
            row.addWidget(button, 0 if stacked else 1)
        main = next((b for b in widgets if b.objectName()), widgets[-1])
        main.setDefault(True)
        main.setFocus()
        layout.addLayout(row)
        fit_to_content(self)

    def _choose(self, index):
        self.choice = index
        self.accept()


def choose(parent, title, message, buttons, icon=None):
    """Index of the clicked button, or None if dismissed."""
    dialog = MessageDialog(parent, title, message, buttons, icon)
    dialog.exec()
    return dialog.choice


def confirm(parent, title, message, action, destructive=False, icon="warning", cancel="Cancel"):
    style = "destructive" if destructive else "primary"
    return choose(parent, title, message, [(cancel, "secondary"), (action, style)], icon) == 1


def inform(parent, title, message, icon="error", button="OK"):
    choose(parent, title, message, [(button, "primary")], icon)


class ProgressDialog(QDialog):
    """Modal progress for a download the user can't cancel (the app update)."""

    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.setWindowTitle("TunnelFlare")
        self.setFixedWidth(400)
        self.setModal(True)
        self._finished = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(0)
        heading = QLabel(title)
        heading.setObjectName("DialogTitle")
        layout.addWidget(heading)
        layout.addSpacing(8)
        self.message = QLabel(message)
        self.message.setObjectName("DialogText")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        layout.addSpacing(18)
        self.bar = QProgressBar()
        self.bar.setObjectName("UpdateProgress")
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)
        layout.addSpacing(8)
        self.detail = QLabel("Connecting…")
        self.detail.setObjectName("FieldHint")
        layout.addWidget(self.detail)
        fit_to_content(self)

    def set_progress(self, done, total):
        mib = 1024 * 1024
        if total > 0:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(done * 100 / total))
            self.detail.setText(f"{done / mib:.1f} of {total / mib:.1f} MB")
        else:
            self.detail.setText(f"{done / mib:.1f} MB")

    def finish(self):
        self._finished = True
        self.accept()

    def reject(self):
        # Esc and the window's close button can't stop a running download
        if self._finished:
            super().reject()
