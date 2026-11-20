"""Packaged-app self-test: proves the bundled runtime works on this machine.

    TunnelFlare --self-test --report report.json [--screenshot shot.png]
                [--expect-cloudflared VERSION] [--e2e]

Exit code 0 means every check passed. Release CI runs this against the installed
artifact on every OS; --e2e opens a real Cloudflare quick tunnel to a local web
server and fetches the page back through the public URL. The test uses a
throwaway config directory, so it never touches the user's tunnels.
"""
import argparse
import http.server
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from tunnelflare_backend.net import ssl_context

REQUIRED_RESOURCES = [
    "add.svg", "alert.svg", "back.svg", "check.svg", "close.svg", "copy.svg", "delete.svg", "edit.svg",
    "open.svg", "qr.svg", "tray.svg", "update.svg",
    "fonts/Inter-Regular.ttf", "fonts/Inter-Medium.ttf", "fonts/Inter-SemiBold.ttf",
    "fonts/Inter-Bold.ttf", "fonts/JetBrainsMono-Regular.ttf",
]
# Every font-weight the stylesheet uses must map to its bundled face. Heavier
# weights are avoided: macOS CoreText maps Inter ExtraBold differently.
EXPECTED_WEIGHT_STYLES = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold"}


class SelfTestError(Exception):
    pass


def run_self_test(argv):
    parser = argparse.ArgumentParser(prog="TunnelFlare --self-test")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--expect-cloudflared", metavar="VERSION")
    parser.add_argument("--e2e", action="store_true", help="open a real Cloudflare quick tunnel")
    args = parser.parse_args(argv)

    home = tempfile.mkdtemp(prefix="tunnelflare-selftest-")
    os.environ["TUNNELFLARE_HOME"] = home
    started = time.monotonic()
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "checks": [],
    }

    def check(name, fn):
        t0 = time.monotonic()
        try:
            detail, ok = fn(), True
        except SelfTestError as exc:
            detail, ok = str(exc), False
        except Exception:
            detail, ok = traceback.format_exc(limit=8), False
        report["checks"].append({"name": name, "ok": ok, "detail": detail, "seconds": round(time.monotonic() - t0, 2)})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)
        return ok

    state = {}

    def bootstrap():
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion
        from tunnelflare_backend import __version__
        from tunnelflare_gui.application import create_application

        state["app"] = create_application([sys.argv[0]])
        report.update(version=__version__, pyside=pyside_version, qt=qVersion(), qt_platform=state["app"].platformName())
        return f"TunnelFlare {__version__}, PySide6 {pyside_version}, Qt {qVersion()}, Fusion style, platform {state['app'].platformName()}"

    if check("bootstrap", bootstrap):
        from tunnelflare_backend.tunnel_manager import TunnelManager
        from tunnelflare_gui.resources import RESOURCE_DIR

        app = state["app"]
        manager = TunnelManager()
        check("resources", lambda: _check_resources(RESOURCE_DIR))
        check("fonts", _check_fonts)
        check("svg-icons", lambda: _check_svg(RESOURCE_DIR))
        check("qr-code", _check_qr)
        check("cloudflared", lambda: _check_cloudflared(manager, args.expect_cloudflared))
        check("main-window", lambda: _check_window(app, args.screenshot))
        if args.e2e:
            check("e2e-quick-tunnel", lambda: _check_e2e(manager))

    report["ok"] = all(c["ok"] for c in report["checks"])
    report["seconds"] = round(time.monotonic() - started, 1)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Self-test {'PASSED' if report['ok'] else 'FAILED'} in {report['seconds']}s", flush=True)
    shutil.rmtree(home, ignore_errors=True)
    return 0 if report["ok"] else 1


def _check_resources(resource_dir):
    missing = [name for name in REQUIRED_RESOURCES if not (resource_dir / name).is_file()]
    if missing:
        raise SelfTestError(f"missing from {resource_dir}: {', '.join(missing)}")
    return f"{len(REQUIRED_RESOURCES)} files in {resource_dir}"


def _check_fonts():
    from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
    from tunnelflare_gui.application import MONO_FONT_FAMILY, UI_FONT_FAMILY

    families = set(QFontDatabase.families())
    missing = [family for family in (UI_FONT_FAMILY, MONO_FONT_FAMILY) if family not in families]
    if missing:
        raise SelfTestError(f"bundled fonts not registered: {missing}")
    resolved = []
    for weight, style in EXPECTED_WEIGHT_STYLES.items():
        font = QFont(UI_FONT_FAMILY)
        font.setWeight(QFont.Weight(weight))
        info = QFontInfo(font)
        if info.family() != UI_FONT_FAMILY or info.styleName() != style:
            raise SelfTestError(f"weight {weight} resolved to {info.family()!r} {info.styleName()!r}, expected {style}")
        resolved.append(f"{weight}={info.styleName()}")
    mono = QFontInfo(QFont(MONO_FONT_FAMILY)).family()
    if mono != MONO_FONT_FAMILY:
        raise SelfTestError(f"monospace resolved to {mono!r}")
    return f"{UI_FONT_FAMILY} {' '.join(resolved)}; {mono}"


def _check_svg(resource_dir):
    from PySide6.QtCore import QSizeF
    from PySide6.QtGui import QIcon
    from tunnelflare_gui.icons import tinted_pixmap

    def painted(image):
        return [(x, y) for y in range(image.height()) for x in range(image.width()) if image.pixelColor(x, y).alpha()]

    for name in ("tray.svg", "add.svg", "delete.svg"):
        image = QIcon(str(resource_dir / name)).pixmap(64, 64).toImage()
        if image.isNull() or not painted(image):
            raise SelfTestError(f"{name} rendered empty (Qt SVG plugins missing?)")
    # Tinted icons must fill their box at any pixel ratio, not just a corner of it
    pixmap = tinted_pixmap("alert.svg", "#ff8a00", 22)
    image = pixmap.toImage()
    pixels = painted(image)
    if pixmap.deviceIndependentSize() != QSizeF(22, 22) or not pixels:
        raise SelfTestError(f"tinted icon is {pixmap.deviceIndependentSize()} and {len(pixels)} painted pixels")
    span = max(x for x, _ in pixels) - min(x for x, _ in pixels) + 1
    if span < image.width() * 0.7:
        raise SelfTestError(f"tinted icon covers {span} of {image.width()} px")
    return "tray.svg, add.svg, delete.svg rendered; tinted icons fill their box"


def _check_qr():
    from PySide6.QtGui import QColor
    from tunnelflare_gui.dialogs.qr_code import render_qr_image

    image = render_qr_image("https://example.trycloudflare.com")
    colors = {image.pixelColor(x, y).name() for y in range(0, image.height(), 5) for x in range(0, image.width(), 5)}
    if image.isNull() or image.width() != image.height() or colors != {QColor("black").name(), QColor("white").name()}:
        raise SelfTestError(f"unexpected QR image {image.width()}x{image.height()} colors {sorted(colors)}")
    return f"{image.width()}x{image.height()} px"


def _check_cloudflared(manager, expected_version):
    bundled = manager._bundled_cloudflared()
    if getattr(sys, "frozen", False) and not (bundled and bundled.is_file()):
        raise SelfTestError(f"bundled cloudflared missing: {bundled}")
    path = manager._get_cloudflared_path()
    if not path:
        raise SelfTestError("cloudflared not found")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=60, **flags)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        raise SelfTestError(f"{path} --version exited {result.returncode}: {output}")
    if expected_version and expected_version not in output:
        raise SelfTestError(f"expected cloudflared {expected_version}, got: {output}")
    return f"{path}: {output}"


def _check_window(app, screenshot):
    from tunnelflare_backend.config_manager import ConfigManager
    from tunnelflare_gui.main_window import MainWindow

    config = ConfigManager()
    config.add_tunnel("self-test", 8080)  # the screenshot shows a tunnel card
    config.set("auto_update_check", False)  # no network calls from the window check
    window = MainWindow()
    try:
        window.show()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.05)
        if not window.isVisible():
            raise SelfTestError("main window did not show")
        detail = f"{window.width()}x{window.height()} on {app.platformName()}"
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(screenshot)):
                raise SelfTestError(f"could not save screenshot {screenshot}")
            detail += f", screenshot {screenshot}"
        return detail
    finally:
        window.refresh_timer.stop()
        window.tray_icon.hide()
        window.hide()


def _check_e2e(manager):
    token = secrets.token_hex(16)
    server = _serve(token)
    context = ssl_context()
    last_response = ["no request sent"]
    tunnel_id = manager.start_tunnel("selftest-e2e", server.server_address[1])
    log = manager.logs_dir / f"{tunnel_id}.log"
    try:
        url = _wait_for(lambda: manager.get_public_url(tunnel_id), 90, "the quick tunnel URL")
        _wait_for(lambda: "Registered tunnel connection" in _read_text(log), 90, "cloudflared to connect to Cloudflare")
        # A brand-new hostname is unknown to DNS for about a second, and looking it up
        # in that window caches the miss (macOS kept it for minutes). Let Cloudflare's
        # resolver publish it before the system resolver ever asks.
        hostname = urllib.parse.urlsplit(url).hostname
        _wait_for(lambda: _dns_published(hostname, context), 60, f"DNS to publish {hostname}")
        _wait_for(lambda: _fetch(url, token, context, last_response), 120, f"{url} to serve the local page")
    except SelfTestError as exc:
        tail = "\n".join(_read_text(log).splitlines()[-40:])
        raise SelfTestError(f"{exc}\nlast response: {last_response[0]}\ncloudflared log (tail):\n{tail}") from None
    finally:
        manager.stop_tunnel(tunnel_id)
        server.shutdown()
        server.server_close()
    if any(t["id"] == tunnel_id for t in manager.get_active_tunnels()):
        raise SelfTestError("tunnel still running after stop")
    return f"{url} served the local page; tunnel stopped"


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _dns_published(hostname, context):
    """True once Cloudflare's public resolver (1.1.1.1, DNS over HTTPS) has an address
    for hostname. If that resolver is unreachable, waits a few seconds and says yes."""
    request = urllib.request.Request(
        f"https://1.1.1.1/dns-query?name={hostname}&type=A", headers={"Accept": "application/dns-json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            return any(answer.get("type") == 1 for answer in json.load(response).get("Answer", []))
    except (OSError, ValueError):
        time.sleep(5)
        return True


def _serve(token):
    body = token.encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # windowed builds have no stderr

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _fetch(url, token, context, last_response):
    request = urllib.request.Request(url, headers={"User-Agent": "TunnelFlare-selftest"})
    try:
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            body = response.read().decode("utf-8", "replace")
            last_response[0] = f"HTTP {response.status}: {body[:80]!r}"
            return response.status == 200 and token in body
    except urllib.error.HTTPError as exc:
        cloudflare_error = re.search(r"Error (?:code:? )?(\d{3,4})", exc.read().decode("utf-8", "replace"))
        last_response[0] = f"HTTP {exc.code}" + (f" (Cloudflare error {cloudflare_error[1]})" if cloudflare_error else "")
    except (OSError, ValueError) as exc:
        last_response[0] = f"{type(exc).__name__}: {exc}"
    return False


def _wait_for(probe, timeout, what):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = probe()
        if result:
            return result
        time.sleep(1)
    raise SelfTestError(f"timed out after {timeout}s waiting for {what}")
