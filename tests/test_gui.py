import re
import socket

import pytest
import qrcode
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton, QSystemTrayIcon

from tunnelflare_backend import updater
from tunnelflare_gui import selftest
from tunnelflare_gui.application import create_application
from tunnelflare_gui.dialogs.qr_code import render_qr_image
from tunnelflare_gui.dialogs.tunnel_dialog import TunnelDialog
from tunnelflare_gui.styles import Styles


@pytest.fixture(scope="session")
def app(qapp):
    return create_application([])


@pytest.fixture
def window(app, qtbot):
    from tunnelflare_gui.main_window import MainWindow

    main_window = MainWindow()
    qtbot.addWidget(main_window)
    yield main_window
    main_window._quitting = True  # let qtbot close it without quitting the test app
    main_window.refresh_timer.stop()
    main_window.tray_icon.hide()
    main_window.tunnel_manager.stop_all()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def test_every_stylesheet_weight_uses_its_bundled_face(app):
    # Identical typography on every OS: each weight in the stylesheet must
    # resolve to the matching bundled Inter face, not a system font or a fallback.
    used = {int(weight) for weight in re.findall(r"font-weight:\s*(\d+)", Styles.STYLESHEET)}
    assert used <= set(selftest.EXPECTED_WEIGHT_STYLES)
    selftest._check_fonts()


def test_scrollbar_stays_out_of_the_cards(window, qtbot):
    home = window.home_view
    add_button = home.findChild(QPushButton, "AddButton")
    bar = home.scroll_area.verticalScrollBar()
    window.show()

    def right_edge(widget):
        return widget.mapTo(window, QPoint(widget.width(), 0)).x()

    def first_card():
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        return home.container_layout.itemAt(0).widget()

    window.config_manager.add_tunnel("api", 3000)
    home.refresh()
    qtbot.waitUntil(lambda: not bar.isVisible() and right_edge(first_card()) == right_edge(add_button))

    for number in range(10):
        window.config_manager.add_tunnel(f"service-{number}", 4000 + number)
    home.refresh()
    qtbot.waitUntil(bar.isVisible)
    # Cards keep their width and alignment; the scrollbar sits in the margin beside them.
    qtbot.waitUntil(lambda: right_edge(first_card()) == right_edge(add_button))
    assert bar.mapTo(window, QPoint(0, 0)).x() > right_edge(first_card())


def test_home_cards_are_updated_in_place(window, fake_cloudflared, listening_port, qtbot):
    window.config_manager.add_tunnel("api", listening_port)
    window.home_view.refresh()
    card = window.home_view.rows["api"]
    assert card.badge.text() == "OFFLINE"

    window.tunnel_manager.start_tunnel("api", listening_port)
    qtbot.waitUntil(lambda: window.home_view.refresh() or card.badge.text() == "ONLINE", timeout=15_000)
    assert window.home_view.rows["api"] is card


def test_cards_open_from_the_keyboard(window, qtbot):
    window.config_manager.add_tunnel("api", 3000)
    window.home_view.refresh()

    with qtbot.waitSignal(window.home_view.tunnel_clicked) as opened:
        qtbot.keyClick(window.home_view.rows["api"], Qt.Key_Return)
    assert opened.args == ["api"]


def test_failed_start_reports_error_and_unlocks_controls(window, qtbot, monkeypatch, listening_port):
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: errors.append(text))
    monkeypatch.setattr(window.tunnel_manager, "_get_cloudflared_path", lambda: None)
    window.config_manager.add_tunnel("api", listening_port)
    window.go_to_detail("api")

    window.detail_view.toggle_btn.click()
    assert not window.detail_view.delete_btn.isEnabled()

    qtbot.waitUntil(lambda: bool(errors), timeout=10_000)
    assert "cloudflared is not installed" in errors[0]
    assert window.detail_view.toggle_btn.isEnabled()
    assert window.detail_view.delete_btn.isEnabled()
    assert window.detail_view.toggle_btn.text() == "Turn ON"


def test_delete_and_edit_stay_locked_until_start_finishes(window, qtbot, fake_cloudflared, listening_port):
    window.config_manager.add_tunnel("api", listening_port)
    window.go_to_detail("api")
    view = window.detail_view
    assert view.edit_btn.isEnabled()

    view.toggle_btn.click()
    assert not view.delete_btn.isEnabled() and not view.edit_btn.isEnabled()

    qtbot.waitUntil(view.delete_btn.isEnabled, timeout=15_000)
    assert view.toggle_btn.text() == "Stop Tunnel"
    assert not view.edit_btn.isEnabled()  # running tunnels can't be edited
    assert [t["name"] for t in window.tunnel_manager.get_active_tunnels()] == ["api"]


def test_link_buttons_wait_until_the_tunnel_connects(window, qtbot, fake_cloudflared, listening_port):
    window.config_manager.add_tunnel("api", listening_port)
    window.go_to_detail("api")
    view = window.detail_view

    fake_cloudflared(url_delay=60)
    window.tunnel_manager.start_tunnel("api", listening_port)
    view.refresh_state()
    assert view.url_text.text() == "Allocating URL..."
    assert not view.open_btn.isEnabled() and not view.qr_btn.isEnabled()

    window.tunnel_manager.stop_all()
    fake_cloudflared()
    window.tunnel_manager.start_tunnel("api", listening_port)
    qtbot.waitUntil(lambda: view.refresh_state() or view.open_btn.isEnabled(), timeout=15_000)
    assert view.badge.text() == "ONLINE" and view.qr_btn.isEnabled()
    assert view.url_text.text() == "fake-tunnel-test.trycloudflare.com"
    assert view.url_text.toolTip() == "https://fake-tunnel-test.trycloudflare.com"


def test_starting_with_nothing_listening_asks_first(window, fake_cloudflared, monkeypatch):
    port = free_port()
    asked = []
    monkeypatch.setattr(window, "_confirm_start_without_server", lambda config: asked.append(config["port"]) or False)
    window.config_manager.add_tunnel("api", port)

    window.toggle_tunnel("api")

    assert asked == [port]
    assert window.tunnel_manager.get_active_tunnels() == []


def test_logs_keep_the_reader_position(window, monkeypatch):
    logs = ["\n".join(f"cloudflared line {number}" for number in range(300))]
    monkeypatch.setattr(window.tunnel_manager, "get_logs_by_name", lambda name: logs[0])
    window.show()
    window.config_manager.add_tunnel("api", 3000)
    window.go_to_detail("api")
    bar = window.detail_view.log_display.verticalScrollBar()
    assert bar.value() == bar.maximum() > 0  # starts at the newest line

    bar.setValue(10)  # the reader scrolls up
    logs[0] += "\ncloudflared line 300"
    window.detail_view.update_logs()
    assert bar.value() == 10

    bar.setValue(bar.maximum())  # back at the end: follow new lines again
    logs[0] += "\ncloudflared line 301"
    window.detail_view.update_logs()
    assert bar.value() == bar.maximum()


def test_closing_without_a_system_tray_quits_instead_of_hiding(window, qtbot, monkeypatch):
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    quit_requests = []
    monkeypatch.setattr(window, "request_quit", lambda: quit_requests.append(True))
    window.show()

    window.close()

    qtbot.waitUntil(lambda: bool(quit_requests))
    assert window.isVisible()  # never hidden into a tray that doesn't exist


def test_closing_with_a_system_tray_hides_to_it(window, qtbot, monkeypatch):
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    quit_requests = []
    monkeypatch.setattr(window, "request_quit", lambda: quit_requests.append(True))
    window.show()

    window.close()

    qtbot.wait(50)
    assert not window.isVisible() and not quit_requests
    assert window.config_manager.get("tray_hint_shown") is True


def test_quitting_with_running_tunnels_lets_the_user_decide(window, fake_cloudflared, listening_port, monkeypatch):
    window.config_manager.add_tunnel("api", listening_port)
    window.tunnel_manager.start_tunnel("api", listening_port)

    monkeypatch.setattr(window, "_ask_quit_choice", lambda count: None)
    assert window.eventFilter(QApplication.instance(), QEvent(QEvent.Quit)) is True  # quit vetoed
    assert window.tunnel_manager.get_active_tunnels()

    monkeypatch.setattr(window, "_ask_quit_choice", lambda count: "keep")
    assert window._confirm_quit() is True
    assert window.tunnel_manager.get_active_tunnels()

    monkeypatch.setattr(window, "_ask_quit_choice", lambda count: "stop")
    assert window._confirm_quit() is True
    assert window.tunnel_manager.get_active_tunnels() == []


def test_tray_menu_switches_tunnels(window, qtbot, fake_cloudflared, listening_port):
    window.config_manager.add_tunnel("api", listening_port)
    window._update_tray(force=True)

    def tunnel_action():
        return next(action for action in window.tray_menu.actions() if action.text().startswith("api"))

    assert tunnel_action().isCheckable() and not tunnel_action().isChecked()
    tunnel_action().trigger()
    qtbot.waitUntil(lambda: not window._busy and bool(window.tunnel_manager.get_active_tunnels()), timeout=15_000)

    window._update_tray(force=True)
    assert tunnel_action().isChecked()
    assert "1 tunnel running" in window.tray_icon.toolTip()


def test_tunnel_dialog_rejects_names_already_in_use(window, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    window.config_manager.add_tunnel("my api", 3000)

    dialog = TunnelDialog(window, window.config_manager)
    dialog.name_input.setText("My_API")
    dialog.port_input.setText("4000")
    dialog.validate_and_accept()
    assert dialog.result() != QDialog.Accepted
    assert "my api" in warnings[0]

    # Editing may keep the tunnel's own name; the options come back with the data
    edit = TunnelDialog(window, window.config_manager, window.config_manager.get_tunnel("my api"))
    edit.port_input.setText("5173")
    edit.https_check.setChecked(True)
    edit.rewrite_check.setChecked(True)
    edit.validate_and_accept()
    assert edit.result() == QDialog.Accepted
    assert edit.get_data() == {"name": "my api", "port": 5173, "protocol": "https", "rewrite_host": True}


def test_found_update_shows_a_banner_until_dismissed(window, qtbot, monkeypatch):
    release = updater.Release(
        version="9.9.9", page_url="https://example.invalid/releases", notes="",
        asset_name=None, asset_url=None, asset_size=None, checksums_url=None,
    )
    monkeypatch.setattr(updater, "check_for_update", lambda current, timeout=15: release)
    banner = window.home_view.banner_container

    window.check_for_updates(manual=False)
    qtbot.waitUntil(lambda: banner.isVisibleTo(window.home_view), timeout=5_000)
    assert "9.9.9" in window.home_view.update_label.text()

    window.home_view._dismiss_update()
    assert not banner.isVisibleTo(window.home_view)
    assert window.config_manager.get("dismissed_update") == "9.9.9"


def test_qr_image_paints_the_encoded_matrix(app):
    url = "https://fake-tunnel-test.trycloudflare.com"
    image = render_qr_image(url)

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    assert image.width() == image.height() == len(matrix) * 10
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            assert (image.pixelColor(x * 10 + 5, y * 10 + 5).value() == 0) == dark, (x, y)
