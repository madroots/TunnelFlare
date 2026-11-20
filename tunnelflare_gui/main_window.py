import sys
import tempfile
import threading
import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QMessageBox, QProgressDialog, QStackedWidget, QSystemTrayIcon
)

from tunnelflare_backend import __version__, updater
from tunnelflare_backend.config_manager import ConfigManager
from tunnelflare_backend.tunnel_manager import TunnelManager
from .components.tunnel_row import status_style
from .dialogs.tunnel_dialog import TunnelDialog
from .resources import RESOURCE_DIR
from .views.detail_view import DetailView
from .views.home_view import HomeView

MIN_HEIGHT = 600  # fits a 1280x720 screen with a taskbar
PREFERRED_HEIGHT = 700
UPDATE_CHECK_INTERVAL = 24 * 3600


class MainWindow(QMainWindow):
    # Results from worker threads; Qt queues them to the GUI thread.
    toggle_finished = Signal(str, str)  # tunnel name, error message or ""
    update_check_finished = Signal(object, str, bool)  # Release or None, error, manual check
    update_progress = Signal(int, int)  # bytes downloaded, total bytes
    update_downloaded = Signal(str, str)  # package path or "", error message or ""

    def __init__(self):
        super().__init__()
        self.setObjectName("MainWindow")
        
        self.config_manager = ConfigManager()
        self.tunnel_manager = TunnelManager()
        self._busy = {}  # tunnel name -> "Starting..." / "Stopping..." while a worker runs
        self._quitting = False
        self._tray_signature = None
        self._update_checking = False
        self._release = None  # newer release found by the update check
        self._update_progress_dialog = None
        
        self.setup_ui()
        self.setup_tray()
        
        # Navigation Stack
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack) # self.stack is the central widget
        
        # Views
        self.home_view = HomeView(self.config_manager, self.tunnel_manager)
        self.detail_view = DetailView(self.tunnel_manager)
        
        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.detail_view)
        
        # Signals
        self.home_view.add_requested.connect(self.show_add_dialog)
        self.home_view.tunnel_clicked.connect(self.go_to_detail)
        self.home_view.update_requested.connect(self.start_update)
        self.home_view.update_dismissed.connect(self._dismiss_update)
        self.detail_view.back_requested.connect(self.go_home)
        self.detail_view.toggle_requested.connect(self.toggle_tunnel)
        self.detail_view.edit_requested.connect(self.show_edit_dialog)
        self.toggle_finished.connect(self._on_toggle_finished)
        self.update_check_finished.connect(self._on_update_check_finished)
        self.update_progress.connect(self._on_update_progress)
        self.update_downloaded.connect(self._on_update_downloaded)

        # Every way of quitting (tray, Cmd+Q, closing without a tray) passes the Quit
        # event; eventFilter asks what to do with running tunnels.
        app = QApplication.instance()
        app.installEventFilter(self)
        if sys.platform == "darwin":
            # Clicking the Dock icon re-activates the app: bring back a hidden window
            app.applicationStateChanged.connect(self._on_application_state)
        
        # Loop
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_current_view)
        self.refresh_timer.start(2000)
        
        self.refresh_current_view()
        self._schedule_update_check()

    def setup_ui(self):
        self.setWindowTitle("TunnelFlare")
        self.setFixedWidth(420)
        self.setMinimumHeight(MIN_HEIGHT)
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry().height() - 80 if screen else PREFERRED_HEIGHT
        self.resize(420, max(MIN_HEIGHT, min(PREFERRED_HEIGHT, available)))
    
    def setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon(str(RESOURCE_DIR / "tray.svg"))
        if sys.platform == "darwin":
            icon.setIsMask(True)  # menu bar template icon, tinted for light and dark menu bars
        self.tray_icon.setIcon(icon)
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(lambda: self._update_tray(force=True))
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self._update_tray(active_tunnels=[], force=True)
        self.tray_icon.show()

    def _update_tray(self, active_tunnels=None, force=False):
        """Tray tooltip plus a menu with an on/off switch per tunnel."""
        if active_tunnels is None:
            active_tunnels = self.tunnel_manager.get_active_tunnels()
        running = {t['name']: t for t in active_tunnels}
        tunnels = self.config_manager.get_tunnels()
        rows = [(t['name'], status_style(running.get(t['name']))[0], t['name'] in self._busy) for t in tunnels]
        auto_check = bool(self.config_manager.get("auto_update_check", True))

        count = len(running)
        self.tray_icon.setToolTip(
            f"TunnelFlare: {count} tunnel{'s' if count != 1 else ''} running" if count else "TunnelFlare: no tunnels running"
        )
        signature = (rows, auto_check)
        if not force and signature == self._tray_signature:
            return
        self._tray_signature = signature

        menu = self.tray_menu
        menu.clear()
        if not rows:
            menu.addAction("No tunnels yet").setEnabled(False)
        for name, status, busy in rows:
            action = menu.addAction(f"{name}  ·  {status}")
            action.setCheckable(True)
            action.setChecked(name in running)
            action.setEnabled(not busy)
            action.triggered.connect(lambda checked=False, tunnel=name: self.toggle_tunnel(tunnel))
        menu.addSeparator()
        menu.addAction("Show TunnelFlare", self.show_window)
        menu.addAction("Check for Updates…", lambda: self.check_for_updates(manual=True))
        auto = menu.addAction("Check for Updates Automatically")
        auto.setCheckable(True)
        auto.setChecked(auto_check)
        auto.toggled.connect(lambda enabled: self.config_manager.set("auto_update_check", enabled))
        menu.addSeparator()
        menu.addAction("Quit TunnelFlare", self.request_quit)

    def refresh_current_view(self):
        active_tunnels = self.tunnel_manager.get_active_tunnels()
        if self.stack.currentWidget() == self.home_view:
            self.home_view.refresh(active_tunnels)
        elif self.stack.currentWidget() == self.detail_view:
            self.detail_view.refresh_state(active_tunnels)
        self._update_tray(active_tunnels)

    def go_to_detail(self, name):
        self.detail_view.load_tunnel(name)
        self._sync_busy_state()
        self.stack.setCurrentWidget(self.detail_view)

    def go_home(self):
        self.detail_view.stop() # Stop logs
        self.stack.setCurrentWidget(self.home_view)
        self.home_view.refresh()

    def show_add_dialog(self):
        dialog = TunnelDialog(self, self.config_manager)
        if dialog.exec():
            data = dialog.get_data()
            self.config_manager.add_tunnel(data['name'], data['port'], data['protocol'], data['rewrite_host'])
            self.home_view.refresh() # Immediate update

    def show_edit_dialog(self, name):
        tunnel = self.config_manager.get_tunnel(name)
        if tunnel is None:
            return
        dialog = TunnelDialog(self, self.config_manager, tunnel)
        if dialog.exec():
            data = dialog.get_data()
            self.config_manager.update_tunnel(name, data['name'], data['port'], data['protocol'], data['rewrite_host'])
            self.go_to_detail(data['name'])

    def toggle_tunnel(self, name):
        if name in self._busy:
            return
        running = next((t for t in self.tunnel_manager.get_active_tunnels() if t['name'] == name), None)
        if running:
            label = "Stopping..."
            def action():
                self.tunnel_manager.stop_tunnel(running['id'])
        else:
            config = self.config_manager.get_tunnel(name)
            if config is None:
                return
            if not self.tunnel_manager.is_port_listening(config['port']) and not self._confirm_start_without_server(config):
                return
            label = "Starting..."
            def action():
                self.tunnel_manager.start_tunnel(
                    config['name'], config['port'], config.get('protocol', 'http'), config.get('rewrite_host', False)
                )

        # Immediate UI Feedback; also locks Delete and Edit until the worker reports back
        self._busy[name] = label
        self._sync_busy_state()
        self._update_tray()

        def run_action():
            error_msg = ""
            try:
                action()
            except Exception as e:
                error_msg = str(e) or type(e).__name__
            self.toggle_finished.emit(name, error_msg)

        threading.Thread(target=run_action, daemon=True).start()

    def _confirm_start_without_server(self, config):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("Nothing Is Listening")
        box.setText(f"Nothing is listening on port {config['port']} yet.")
        box.setInformativeText("Visitors will see an error page until your app runs on that port. Start the tunnel anyway?")
        start = box.addButton("Start Anyway", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        return box.clickedButton() is start

    def _sync_busy_state(self):
        name = self.detail_view.current_tunnel_name
        self.detail_view.set_busy(name in self._busy, self._busy.get(name))

    def _on_toggle_finished(self, name, error_msg):
        self._busy.pop(name, None)
        self._sync_busy_state()
        self.refresh_current_view()
        if error_msg:
            QMessageBox.critical(self, "Tunnel Error", f"Failed to toggle tunnel “{name}”: {error_msg}")

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def _on_application_state(self, state):
        if state == Qt.ApplicationActive and not self.isVisible() and not self._quitting:
            self.show_window()

    # Quitting -----------------------------------------------------------------

    def request_quit(self):
        QApplication.quit()  # eventFilter confirms first

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Quit and watched is QApplication.instance() and not self._quitting:
            if not self._confirm_quit():
                return True  # stay running
            self._quitting = True
        return super().eventFilter(watched, event)

    def _confirm_quit(self):
        """Ask what happens to running tunnels; False cancels quitting."""
        running = self.tunnel_manager.get_active_tunnels()
        if not running:
            return True
        choice = self._ask_quit_choice(len(running))
        if choice == "stop":
            self.tunnel_manager.stop_all()
        return choice in ("stop", "keep")

    def _ask_quit_choice(self, count):
        """"stop", "keep" or None (cancel) for quitting with `count` running tunnels."""
        self.show_window()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Quit TunnelFlare")
        box.setText(f"{count} tunnel{'s are' if count != 1 else ' is'} still running.")
        box.setInformativeText(
            "Running tunnels keep your local apps reachable from the internet after "
            "TunnelFlare quits. TunnelFlare finds them again the next time it starts."
        )
        stop = box.addButton("Stop Tunnels and Quit", QMessageBox.DestructiveRole)
        keep = box.addButton("Keep Running and Quit", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(stop)
        box.exec()
        clicked = box.clickedButton()
        return "stop" if clicked is stop else "keep" if clicked is keep else None

    def closeEvent(self, event):
        if self._quitting:
            event.accept()
            return
        if QSystemTrayIcon.isSystemTrayAvailable() and self.tray_icon.isVisible():
            # Keep running in the tray; tunnels stay up
            event.ignore()
            self.hide()
            if not self.config_manager.get("tray_hint_shown"):
                self.tray_icon.showMessage(
                    "TunnelFlare", "TunnelFlare keeps running here. Use this icon to show it or quit.",
                    QSystemTrayIcon.Information, 4000,
                )
                self.config_manager.set("tray_hint_shown", True)
            return
        # No system tray to keep running in: closing the window quits the app
        event.ignore()
        QTimer.singleShot(0, self.request_quit)

    # Updates ------------------------------------------------------------------

    def _schedule_update_check(self):
        if not getattr(sys, "frozen", False) or not self.config_manager.get("auto_update_check", True):
            return
        if time.time() - self.config_manager.get("last_update_check", 0) > UPDATE_CHECK_INTERVAL:
            QTimer.singleShot(5000, lambda: self.check_for_updates(manual=False))

    def check_for_updates(self, manual=True):
        if self._update_checking:
            return
        self._update_checking = True

        def run():
            try:
                release, error = updater.check_for_update(__version__), ""
            except updater.UpdateError as exc:
                release, error = None, str(exc)
            except Exception as exc:  # an update check must never take the app down
                release, error = None, f"{type(exc).__name__}: {exc}"
            self.update_check_finished.emit(release, error, manual)

        threading.Thread(target=run, daemon=True).start()

    def _on_update_check_finished(self, release, error, manual):
        self._update_checking = False
        if error:
            if manual:
                QMessageBox.warning(self, "Update Check Failed", error)
            return
        self.config_manager.set("last_update_check", time.time())
        if release is None:
            if manual:
                QMessageBox.information(self, "You're Up to Date", f"TunnelFlare {__version__} is the latest version.")
            return
        self._release = release
        if manual:
            self.home_view.show_update(release.version)
            self.start_update()
        elif self.config_manager.get("dismissed_update") != release.version:
            self.home_view.show_update(release.version)
            if not self.isVisible():
                self.tray_icon.showMessage("TunnelFlare", f"TunnelFlare {release.version} is available.")

    def _dismiss_update(self):
        if self._release:
            self.config_manager.set("dismissed_update", self._release.version)

    def start_update(self):
        release = self._release
        if release is None:
            return
        supported, reason = updater.install_support()
        if not supported or not release.asset_url:
            box = QMessageBox(self)
            box.setWindowTitle("Update Available")
            box.setText(f"TunnelFlare {release.version} is available.")
            box.setInformativeText(reason or "There is no automatic update for this system yet.")
            download = box.addButton("Open Download Page", QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Close)
            box.exec()
            if box.clickedButton() is download:
                QDesktopServices.openUrl(QUrl(release.page_url))
            return

        box = QMessageBox(self)
        box.setWindowTitle("Update TunnelFlare")
        box.setText(f"Update to TunnelFlare {release.version}?")
        box.setInformativeText("TunnelFlare restarts to finish the update. Running tunnels stay online.")
        update = box.addButton("Update and Restart", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is not update:
            return

        progress = QProgressDialog(f"Downloading TunnelFlare {release.version}…", None, 0, 0, self)
        progress.setWindowTitle("Updating TunnelFlare")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        self._update_progress_dialog = progress

        def run():
            try:
                folder = Path(tempfile.mkdtemp(prefix="tunnelflare-update-"))
                package = updater.download_release(release, folder, progress=self.update_progress.emit)
                self.update_downloaded.emit(str(package), "")
            except updater.UpdateError as exc:
                self.update_downloaded.emit("", str(exc))
            except Exception as exc:
                self.update_downloaded.emit("", f"{type(exc).__name__}: {exc}")

        threading.Thread(target=run, daemon=True).start()

    def _on_update_progress(self, done, total):
        dialog = self._update_progress_dialog
        if dialog and total > 0:
            dialog.setMaximum(100)
            dialog.setValue(int(done * 100 / total))

    def _on_update_downloaded(self, package, error):
        if self._update_progress_dialog:
            self._update_progress_dialog.close()
            self._update_progress_dialog = None
        if error:
            QMessageBox.warning(self, "Update Failed", error)
            return
        try:
            updater.install(Path(package), relaunch=True)
        except Exception as exc:
            QMessageBox.warning(self, "Update Failed", str(exc) or type(exc).__name__)
            return
        # The installer replaces the app and starts the new version; tunnels keep running.
        self._quitting = True
        QApplication.quit()
