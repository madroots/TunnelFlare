from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from tunnelflare_backend.config_manager import tunnel_id_for
from tunnelflare_backend.tunnel_manager import TunnelManager
from ..components.tunnel_row import restyle, set_flag, set_text
from .message_dialog import fit_to_content


class TunnelDialog(QDialog):
    """Add a tunnel, or edit an existing one when `tunnel` (its saved config) is given.
    Problems show under their field once the user tries to save, then update live."""

    def __init__(self, parent=None, config_manager=None, tunnel=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.original_name = tunnel['name'] if tunnel else None
        self.setWindowTitle("TunnelFlare")
        self.setFixedWidth(400)
        self._show_errors = False
        self._port_status = None  # (port, listening) from the last check
        self._port_timer = QTimer(self)
        self._port_timer.setSingleShot(True)
        self._port_timer.setInterval(250)
        self._port_timer.timeout.connect(self._check_port)
        self.setup_ui()
        if tunnel:
            self.name_input.setText(tunnel['name'])
            self.port_input.setText(str(tunnel['port']))
            self.https_check.setChecked(tunnel.get('protocol') == 'https')
            self.rewrite_check.setChecked(bool(tunnel.get('rewrite_host')))
        self.name_input.textChanged.connect(self._revalidate)
        self.port_input.textChanged.connect(self._revalidate)
        self._check_port()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 24)
        layout.setSpacing(0)

        title = QLabel("Edit Tunnel" if self.original_name else "New Tunnel")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        layout.addSpacing(6)
        intro = QLabel("Give a local app a public HTTPS link.")
        intro.setObjectName("DialogText")
        layout.addWidget(intro)
        layout.addSpacing(22)

        layout.addWidget(QLabel("Name", objectName="FieldLabel"))
        layout.addSpacing(6)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. backend-api")
        layout.addWidget(self.name_input)
        self.name_error = self._message("FieldError")
        layout.addWidget(self.name_error)
        layout.addSpacing(14)

        layout.addWidget(QLabel("Local port", objectName="FieldLabel"))
        layout.addSpacing(6)
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("3000")
        self.port_input.setMaxLength(5)
        layout.addWidget(self.port_input)
        self.port_hint = self._message("FieldHint")
        layout.addWidget(self.port_hint)
        layout.addSpacing(18)

        self.https_check = QCheckBox("My local server uses HTTPS")
        layout.addWidget(self.https_check)
        layout.addWidget(self._hint("Self-signed certificates are accepted."))
        layout.addSpacing(10)
        self.rewrite_check = QCheckBox("Send requests as “localhost”")
        layout.addWidget(self.rewrite_check)
        layout.addWidget(self._hint(
            "Rewrites the Host header. Fixes “Invalid Host header” and “Blocked request” "
            "errors from Vite, webpack and Django dev servers."
        ))
        layout.addSpacing(24)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(44)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setAutoDefault(False)
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save" if self.original_name else "Add Tunnel")
        self.save_btn.setObjectName("PrimaryAction")
        self.save_btn.setMinimumHeight(44)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.validate_and_accept)
        buttons.addWidget(self.cancel_btn, 1)
        buttons.addWidget(self.save_btn, 1)
        layout.addLayout(buttons)

    @staticmethod
    def _message(style):
        label = QLabel()
        label.setObjectName(style)
        label.setWordWrap(True)
        label.setContentsMargins(2, 6, 0, 0)
        label.hide()
        return label

    @staticmethod
    def _hint(text):
        hint = QLabel(text)
        hint.setObjectName("HintLabel")
        hint.setWordWrap(True)
        hint.setContentsMargins(28, 2, 0, 0)
        return hint

    # Validation ---------------------------------------------------------------

    def name_problem(self):
        name = self.name_input.text().strip()
        if not name:
            return "Enter a name for the tunnel."
        conflict = self.config_manager.name_conflict(name, ignore=self.original_name) if self.config_manager else None
        if conflict == name:
            return f"A tunnel named “{name}” already exists."
        if conflict:
            return (f"Too similar to “{conflict}”: both would use the same log files "
                    f"({tunnel_id_for(name)}).")
        return ""

    def port(self):
        text = self.port_input.text().strip()
        return int(text) if text.isdigit() and 1 <= int(text) <= 65535 else None

    def port_problem(self):
        return "" if self.port() else "Enter a port from 1 to 65535."

    def _revalidate(self):
        if self._show_errors:
            self._show_name_problem(self.name_problem())
        if self.port():
            self._port_timer.start()  # check the new port once typing pauses
        self._show_port_message()
        fit_to_content(self)

    def _show_name_problem(self, problem):
        set_text(self.name_error, problem)
        self.name_error.setVisible(bool(problem))
        set_flag(self.name_input, "invalid", bool(problem))

    def _show_port_message(self):
        problem = self.port_problem() if self._show_errors else ""
        set_flag(self.port_input, "invalid", bool(problem))
        status = self._port_status
        if problem:
            set_text(self.port_hint, problem)
            restyle(self.port_hint, "FieldError")
        elif self.port() is None:
            self.port_hint.hide()
            return
        elif not status or status[0] != self.port():
            return  # a check for the new port is pending; keep the current message
        elif status[1]:
            set_text(self.port_hint, f"●  Your app is running on port {status[0]}.")
            restyle(self.port_hint, "FieldHintOk")
        else:
            set_text(self.port_hint, f"Nothing is running on port {status[0]} yet. You can still save.")
            restyle(self.port_hint, "FieldHint")
        self.port_hint.show()

    def _check_port(self):
        port = self.port()
        self._port_status = (port, TunnelManager.is_port_listening(port)) if port else None
        self._show_port_message()
        fit_to_content(self)

    def validate_and_accept(self):
        self._show_errors = True
        name_problem, port_problem = self.name_problem(), self.port_problem()
        self._show_name_problem(name_problem)
        self._show_port_message()
        fit_to_content(self)
        if name_problem:
            self.name_input.setFocus()
        elif port_problem:
            self.port_input.setFocus()
        else:
            self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "port": int(self.port_input.text().strip()),
            "protocol": "https" if self.https_check.isChecked() else "http",
            "rewrite_host": self.rewrite_check.isChecked(),
        }
