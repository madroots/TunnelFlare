import re

import pytest
import qrcode
from PySide6.QtWidgets import QMessageBox

from tunnelflare_gui import selftest
from tunnelflare_gui.application import create_application
from tunnelflare_gui.dialogs.qr_code import render_qr_image
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
    main_window.refresh_timer.stop()
    main_window.tray_icon.hide()
    main_window.tunnel_manager.stop_all()


def test_every_stylesheet_weight_uses_its_bundled_face(app):
    # Identical typography on every OS: each weight in the stylesheet must
    # resolve to the matching bundled Inter face, not a system font or a fallback.
    used = {int(weight) for weight in re.findall(r"font-weight:\s*(\d+)", Styles.STYLESHEET)}
    assert used <= set(selftest.EXPECTED_WEIGHT_STYLES)
    selftest._check_fonts()


def test_failed_start_reports_error_and_unlocks_controls(window, qtbot, monkeypatch):
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda parent, title, text: errors.append(text))
    monkeypatch.setattr(window.tunnel_manager, "_get_cloudflared_path", lambda: None)
    window.config_manager.add_tunnel("api", 3000)
    window.go_to_detail("api")

    window.detail_view.toggle_btn.click()
    assert not window.detail_view.delete_btn.isEnabled()

    qtbot.waitUntil(lambda: bool(errors), timeout=10_000)
    assert "cloudflared is not installed" in errors[0]
    assert window.detail_view.toggle_btn.isEnabled()
    assert window.detail_view.delete_btn.isEnabled()
    assert window.detail_view.toggle_btn.text() == "Turn ON"


def test_delete_stays_locked_until_start_finishes(window, qtbot, fake_cloudflared):
    window.config_manager.add_tunnel("api", 3000)
    window.go_to_detail("api")

    window.detail_view.toggle_btn.click()
    assert not window.detail_view.delete_btn.isEnabled()

    qtbot.waitUntil(window.detail_view.delete_btn.isEnabled, timeout=15_000)
    assert window.detail_view.toggle_btn.text() == "Stop Tunnel"
    assert [t["name"] for t in window.tunnel_manager.get_active_tunnels()] == ["api"]


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
