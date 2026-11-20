import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tunnelflare_backend import updater
from tunnelflare_backend.updater import Release, UpdateError

POSIX = os.name == "posix"
posix_only = pytest.mark.skipif(not POSIX, reason="needs /bin/sh and POSIX permissions")
IS_ROOT = POSIX and os.geteuid() == 0
PYTHON = sys.executable  # tests monkeypatch sys.executable to fake app paths
LINUX_ASSET = "TunnelFlare-0.3.0-linux-x86_64.AppImage"


# --------------------------------------------------------------------------- fixtures


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        fake = self.server.fake
        fake.requests.append((self.path, dict(self.headers)))
        route = fake.routes.get(self.path)
        if route is None:
            self.send_error(404)
            return
        status, headers, body = route
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        if fake.send_length:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class FakeGitHub:
    """A local stand-in for the GitHub releases API and its download URLs."""

    def __init__(self, base):
        self.base = base
        self.routes = {}
        self.requests = []
        self.send_length = True

    def publish(self, tag, assets, checksums="auto", release_status=200, release_body=None):
        listed = []
        for name, data in assets.items():
            self._serve(name, data)
            listed.append(
                {"name": name, "size": len(data), "browser_download_url": f"{self.base}/download/{name}"}
            )
        if checksums == "auto":
            checksums = "".join(f"{hashlib.sha256(d).hexdigest()}  {n}\n" for n, d in assets.items())
        if checksums is not None:
            self._serve("SHA256SUMS.txt", checksums.encode())
            listed.append({
                "name": "SHA256SUMS.txt",
                "size": len(checksums),
                "browser_download_url": f"{self.base}/download/SHA256SUMS.txt",
            })
        if release_body is None:
            release_body = json.dumps({
                "tag_name": tag,
                "html_url": f"https://github.com/madroots/TunnelFlare/releases/tag/{tag}",
                "body": "Release notes",
                "assets": listed,
            }).encode()
        self.routes["/releases/latest"] = (release_status, {"Content-Type": "application/json"}, release_body)

    def _serve(self, name, data):
        # GitHub answers download URLs with a redirect to its CDN.
        self.routes[f"/download/{name}"] = (302, {"Location": f"{self.base}/files/{name}"}, b"")
        self.routes[f"/files/{name}"] = (200, {"Content-Type": "application/octet-stream"}, data)


@pytest.fixture
def github(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.fake = FakeGitHub(f"http://127.0.0.1:{server.server_address[1]}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("TUNNELFLARE_UPDATE_API", f"{server.fake.base}/releases/latest")
    monkeypatch.setenv("TUNNELFLARE_VERSION_OVERRIDE", "0.2.1")
    yield server.fake
    server.shutdown()
    server.server_close()


def set_platform(monkeypatch, name, machine="x86_64"):
    monkeypatch.setattr(sys, "platform", name)
    monkeypatch.setattr(updater.platform, "machine", lambda: machine)


@pytest.fixture
def linux(monkeypatch):
    set_platform(monkeypatch, "linux")


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)


def wait_for(predicate, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def make_release(github, data=b"new appimage", **overrides):
    fields = {
        "version": "0.3.0",
        "page_url": "",
        "notes": "",
        "asset_name": LINUX_ASSET,
        "asset_url": f"{github.base}/download/{LINUX_ASSET}",
        "asset_size": len(data),
        "checksums_url": f"{github.base}/download/SHA256SUMS.txt",
    }
    fields.update(overrides)
    return Release(**fields)


# --------------------------------------------------------------------------- versions and assets


@pytest.mark.parametrize(("candidate", "current", "expected"), [
    ("0.3.0", "0.2.1", True),
    ("v0.3.0", "0.2.1", True),
    ("0.2.10", "0.2.9", True),
    ("1.0", "0.9.9", True),
    ("0.2.1", "0.2.1", False),
    ("v0.2.1", "0.2.1.0", False),
    ("0.2.0", "0.2.1", False),
    ("0.3.0-rc1", "0.2.1", False),
    ("0.3.0b1", "0.2.1", False),
    ("nightly", "0.2.1", False),
    ("", "0.2.1", False),
    ("0.3.0", "dev", False),
])
def test_is_newer(candidate, current, expected):
    assert updater.is_newer(candidate, current) is expected


@pytest.mark.parametrize(("platform_name", "machine", "expected"), [
    ("win32", "AMD64", "TunnelFlare-1.2.3-windows-x64-setup.exe"),
    ("darwin", "arm64", "TunnelFlare-1.2.3-macos-universal.dmg"),
    ("darwin", "x86_64", "TunnelFlare-1.2.3-macos-universal.dmg"),
    ("linux", "x86_64", "TunnelFlare-1.2.3-linux-x86_64.AppImage"),
    ("linux", "aarch64", None),
    ("freebsd14", "amd64", None),
])
def test_platform_asset_name(monkeypatch, platform_name, machine, expected):
    set_platform(monkeypatch, platform_name, machine)
    assert updater.platform_asset_name("1.2.3") == expected


def test_current_version_override(monkeypatch):
    from tunnelflare_backend import __version__

    monkeypatch.delenv("TUNNELFLARE_VERSION_OVERRIDE", raising=False)
    assert updater.current_version() == __version__
    monkeypatch.setenv("TUNNELFLARE_VERSION_OVERRIDE", "9.9.9")
    assert updater.current_version() == "9.9.9"


# --------------------------------------------------------------------------- release information


def test_fetch_latest_release_parses_github_json(github, linux):
    github.publish("v0.3.0", {LINUX_ASSET: b"linux", "TunnelFlare-0.3.0-macos-universal.dmg": b"mac"})

    release = updater.fetch_latest_release()

    assert release == Release(
        version="0.3.0",
        page_url="https://github.com/madroots/TunnelFlare/releases/tag/v0.3.0",
        notes="Release notes",
        asset_name=LINUX_ASSET,
        asset_url=f"{github.base}/download/{LINUX_ASSET}",
        asset_size=5,
        checksums_url=f"{github.base}/download/SHA256SUMS.txt",
    )
    path, headers = github.requests[-1]
    assert path == "/releases/latest"
    assert headers["User-Agent"] == "TunnelFlare/0.2.1"
    assert headers["Accept"] == "application/vnd.github+json"


def test_release_without_asset_for_this_platform(github, monkeypatch):
    set_platform(monkeypatch, "linux", "aarch64")
    github.publish("v0.3.0", {LINUX_ASSET: b"linux"})

    release = updater.fetch_latest_release()

    assert release.version == "0.3.0"
    assert (release.asset_name, release.asset_url, release.asset_size) == (None, None, None)


def test_check_for_update(github, linux):
    github.publish("v0.3.0", {LINUX_ASSET: b"linux"})
    assert updater.check_for_update("0.2.1").version == "0.3.0"
    assert updater.check_for_update("0.3.0") is None
    assert updater.check_for_update("v0.4") is None


@pytest.mark.parametrize(("status", "body"), [
    (500, b"{}"),
    (404, b'{"message": "Not Found"}'),
    (200, b"<html>not json</html>"),
    (200, b"[]"),
    (200, b'{"assets": []}'),
])
def test_fetch_latest_release_errors(github, status, body):
    github.publish("v0.3.0", {}, release_status=status, release_body=body)
    with pytest.raises(UpdateError):
        updater.fetch_latest_release()


def test_rate_limit_message(github):
    github.publish("v0.3.0", {})
    github.routes["/releases/latest"] = (403, {"X-RateLimit-Remaining": "0"}, b"{}")
    with pytest.raises(UpdateError, match="rate limit"):
        updater.fetch_latest_release()


def test_unreachable_server(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    server.server_close()
    monkeypatch.setenv("TUNNELFLARE_UPDATE_API", f"http://127.0.0.1:{port}/releases/latest")
    with pytest.raises(UpdateError, match="Could not connect"):
        updater.fetch_latest_release(timeout=5)


def test_plain_http_requires_api_override(github, tmp_path, monkeypatch):
    github.publish("v0.3.0", {LINUX_ASSET: b"data"})
    release = make_release(github, b"data")
    monkeypatch.delenv("TUNNELFLARE_UPDATE_API")
    with pytest.raises(UpdateError, match="insecure"):
        updater.download_release(release, tmp_path)
    assert github.requests == []


# --------------------------------------------------------------------------- download


def test_download_verifies_and_reports_progress(github, tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "_CHUNK_SIZE", 1000)
    data = os.urandom(10_500)
    github.publish("v0.3.0", {LINUX_ASSET: data, "other.bin": b"x"})
    calls = []

    path = updater.download_release(make_release(github, data), tmp_path / "dl", progress=lambda *a: calls.append(a))

    assert path == tmp_path / "dl" / LINUX_ASSET
    assert path.read_bytes() == data
    assert not (tmp_path / "dl" / f"{LINUX_ASSET}.part").exists()
    assert calls[0] == (0, len(data))
    assert calls[-1] == (len(data), len(data))
    assert len(calls) == 12
    assert [done for done, _ in calls] == sorted(done for done, _ in calls)
    assert f"/files/{LINUX_ASSET}" in [path for path, _ in github.requests]  # redirect followed


def test_download_progress_total_falls_back_to_asset_size(github, tmp_path):
    data = b"a" * 5000
    github.publish("v0.3.0", {LINUX_ASSET: data})
    github.send_length = False
    calls = []

    updater.download_release(make_release(github, data), tmp_path, progress=lambda *a: calls.append(a))

    assert calls[-1] == (5000, 5000)


def test_download_checksum_mismatch(github, tmp_path):
    github.publish("v0.3.0", {LINUX_ASSET: b"tampered"}, checksums=f"{'0' * 64}  {LINUX_ASSET}\n")
    with pytest.raises(UpdateError, match="SHA-256 mismatch"):
        updater.download_release(make_release(github, b"tampered"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_missing_checksum_line(github, tmp_path):
    other = hashlib.sha256(b"x").hexdigest()
    github.publish("v0.3.0", {LINUX_ASSET: b"data"}, checksums=f"{other}  TunnelFlare-0.3.0-other.zip\n")
    with pytest.raises(UpdateError, match="no checksum"):
        updater.download_release(make_release(github, b"data"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_accepts_binary_mode_checksum_line(github, tmp_path):
    digest = hashlib.sha256(b"data").hexdigest().upper()
    github.publish("v0.3.0", {LINUX_ASSET: b"data"}, checksums=f"# comment\n{digest} *{LINUX_ASSET}\r\n")
    assert updater.download_release(make_release(github, b"data"), tmp_path).read_bytes() == b"data"


def test_download_requires_checksums_and_asset(github, tmp_path):
    with pytest.raises(UpdateError, match="SHA256SUMS"):
        updater.download_release(make_release(github, checksums_url=None), tmp_path)
    with pytest.raises(UpdateError, match="no download"):
        updater.download_release(make_release(github, asset_name=None, asset_url=None), tmp_path)


def test_download_aborted_by_progress_callback(github, tmp_path):
    github.publish("v0.3.0", {LINUX_ASSET: b"data"})

    def cancel(done, total):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        updater.download_release(make_release(github, b"data"), tmp_path, progress=cancel)
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- install_support


def test_install_support_requires_frozen_build(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    supported, reason = updater.install_support()
    assert not supported
    assert "source" in reason


def make_windows_install(tmp_path, monkeypatch, installed):
    app_dir = tmp_path / "Program Files" / "TunnelFlare"
    app_dir.mkdir(parents=True)
    (app_dir / "TunnelFlare.exe").write_bytes(b"exe")
    if installed:
        (app_dir / "unins000.exe").write_bytes(b"uninstaller")
    set_platform(monkeypatch, "win32", "AMD64")
    monkeypatch.setattr(sys, "executable", str(app_dir / "TunnelFlare.exe"))
    return app_dir


def test_install_support_windows_portable_copy(tmp_path, monkeypatch, frozen):
    make_windows_install(tmp_path, monkeypatch, installed=False)
    supported, reason = updater.install_support()
    assert not supported
    assert "portable" in reason


def test_install_support_windows_installed_copy(tmp_path, monkeypatch, frozen):
    make_windows_install(tmp_path, monkeypatch, installed=True)
    assert updater.install_support() == (True, "")


def test_install_support_windows_not_writable(tmp_path, monkeypatch, frozen):
    make_windows_install(tmp_path, monkeypatch, installed=True)
    monkeypatch.setattr(updater, "_dir_writable", lambda path: False)
    supported, reason = updater.install_support()
    assert not supported
    assert "administrator" in reason


def make_mac_bundle(parent, monkeypatch, content="old"):
    executable = parent / "TunnelFlare.app" / "Contents" / "MacOS" / "TunnelFlare"
    executable.parent.mkdir(parents=True)
    executable.write_text(content)
    set_platform(monkeypatch, "darwin", "arm64")
    monkeypatch.setattr(sys, "executable", str(executable))
    return parent / "TunnelFlare.app"


def test_install_support_macos(tmp_path, monkeypatch, frozen):
    make_mac_bundle(tmp_path / "Applications", monkeypatch)
    assert updater.install_support() == (True, "")


def test_install_support_macos_translocated(tmp_path, monkeypatch, frozen):
    make_mac_bundle(tmp_path / "AppTranslocation" / "1A2B" / "d", monkeypatch)
    supported, reason = updater.install_support()
    assert not supported
    assert "Applications folder" in reason


def test_install_support_macos_not_an_app_bundle(tmp_path, monkeypatch, frozen):
    executable = tmp_path / "dist" / "bin" / "x" / "TunnelFlare"
    executable.parent.mkdir(parents=True)
    set_platform(monkeypatch, "darwin")
    monkeypatch.setattr(sys, "executable", str(executable))
    assert updater.install_support()[0] is False


@posix_only
@pytest.mark.skipif(IS_ROOT, reason="root can write to read-only directories")
def test_install_support_macos_read_only_folder(tmp_path, monkeypatch, frozen):
    make_mac_bundle(tmp_path / "Volumes" / "TunnelFlare", monkeypatch)
    folder = tmp_path / "Volumes" / "TunnelFlare"
    folder.chmod(0o555)
    try:
        supported, reason = updater.install_support()
    finally:
        folder.chmod(0o755)
    assert not supported
    assert "Applications folder" in reason


def test_install_support_linux_needs_appimage(monkeypatch, linux, frozen):
    monkeypatch.delenv("APPIMAGE", raising=False)
    supported, reason = updater.install_support()
    assert not supported
    assert "AppImage" in reason


def test_install_support_linux_appimage(tmp_path, monkeypatch, linux, frozen):
    monkeypatch.setenv("APPIMAGE", str(tmp_path / "TunnelFlare.AppImage"))
    assert updater.install_support() == (True, "")


@posix_only
@pytest.mark.skipif(IS_ROOT, reason="root can write to read-only directories")
def test_install_support_linux_read_only_folder(tmp_path, monkeypatch, linux, frozen):
    folder = tmp_path / "opt"
    folder.mkdir()
    monkeypatch.setenv("APPIMAGE", str(folder / "TunnelFlare.AppImage"))
    folder.chmod(0o555)
    try:
        supported, reason = updater.install_support()
    finally:
        folder.chmod(0o755)
    assert not supported
    assert "not writable" in reason


def test_install_refuses_unsupported_copy(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    package = tmp_path / "setup.exe"
    package.write_bytes(b"x")
    with pytest.raises(UpdateError, match="source"):
        updater.install(package)


# --------------------------------------------------------------------------- Windows


class StartedProcesses(list):
    """Processes started through the fake Popen; exit_code is what wait() returns."""

    exit_code = 0


@pytest.fixture
def fake_popen(monkeypatch):
    started = StartedProcesses()

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            self.cmd = cmd
            self.kwargs = kwargs
            started.append(self)

        def wait(self):
            return started.exit_code

    monkeypatch.setattr(updater.subprocess, "Popen", FakePopen)
    return started


@pytest.mark.parametrize(("relaunch", "show_progress"), [(True, True), (False, False)])
def test_windows_installer_command(tmp_path, monkeypatch, frozen, fake_popen, relaunch, show_progress):
    app_dir = make_windows_install(tmp_path, monkeypatch, installed=True)
    package = tmp_path / "Downloads here" / "TunnelFlare-0.3.0-windows-x64-setup.exe"
    package.parent.mkdir()
    package.write_bytes(b"setup")

    updater.install(package, relaunch=relaunch, show_progress=show_progress)

    (popen,) = fake_popen
    expected = [
        str(package.resolve()),
        "/SILENT" if show_progress else "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CURRENTUSER",
        "/CLOSEAPPLICATIONS",
        f"/DIR={app_dir}",
    ]
    if relaunch:
        expected.append("/RELAUNCH=1")
    assert popen.cmd == expected
    assert popen.kwargs["creationflags"] == 0x8 | 0x200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def test_windows_installer_blocking_failure(tmp_path, monkeypatch, frozen, fake_popen):
    make_windows_install(tmp_path, monkeypatch, installed=True)
    package = tmp_path / "setup.exe"
    package.write_bytes(b"setup")
    fake_popen.exit_code = 5

    with pytest.raises(UpdateError, match="exit code 5"):
        updater.install(package, block=True)
    assert fake_popen[0].cmd[-1] == "/RELAUNCH=1"


# --------------------------------------------------------------------------- macOS

_STUBS = {
    "hdiutil": r"""#!/bin/sh
echo "hdiutil $*" >> "$STUB_CALLS"
for last; do :; done
case "$1" in
attach)
    [ -f "$last" ] || exit 1
    mnt=
    prev=
    for arg; do
        [ "$prev" = "-mountpoint" ] && mnt=$arg
        prev=$arg
    done
    mkdir -p "$mnt/TunnelFlare.app/Contents/MacOS" || exit 1
    printf new > "$mnt/TunnelFlare.app/Contents/MacOS/TunnelFlare"
    ln -s /Applications "$mnt/Applications"
    ;;
detach)
    rm -rf "$2/TunnelFlare.app" "$2/Applications"
    ;;
esac
""",
    "ditto": """#!/bin/sh
echo "ditto $*" >> "$STUB_CALLS"
cp -R "$1" "$2"
""",
    "codesign": """#!/bin/sh
echo "codesign $*" >> "$STUB_CALLS"
for last; do :; done
[ "$STUB_CODESIGN_FAIL" = 1 ] && exit 1
[ -d "$last" ]
""",
    "xattr": """#!/bin/sh
echo "xattr $*" >> "$STUB_CALLS"
""",
    "open": """#!/bin/sh
echo "open $*" >> "$STUB_CALLS"
""",
}


@pytest.fixture
def mac_app(tmp_path, monkeypatch, frozen, tunnelflare_home):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, script in _STUBS.items():
        path = stubs / name
        path.write_text(script)
        path.chmod(0o755)
    calls = tmp_path / "calls.txt"
    calls.touch()
    monkeypatch.setenv("STUB_CALLS", str(calls))
    monkeypatch.setenv("PATH", f"{stubs}{os.pathsep}{os.environ['PATH']}")
    bundle = make_mac_bundle(tmp_path / "My Apps", monkeypatch)
    package = tmp_path / "dl dir" / "TunnelFlare-0.3.0-macos-universal.dmg"
    package.parent.mkdir()
    package.write_bytes(b"dmg")

    class App:
        pass

    app = App()
    app.bundle = bundle
    app.package = package
    app.executable = bundle / "Contents" / "MacOS" / "TunnelFlare"
    app.calls = lambda: calls.read_text().splitlines()
    app.log = tunnelflare_home / "update.log"
    return app


@posix_only
@pytest.mark.parametrize("relaunch", [True, False])
def test_macos_helper_replaces_bundle(mac_app, relaunch):
    updater.install(mac_app.package, relaunch=relaunch, block=True)

    assert mac_app.executable.read_text() == "new"
    assert sorted(p.name for p in mac_app.bundle.parent.iterdir()) == ["TunnelFlare.app"]
    calls = mac_app.calls()
    commands = [call.split()[0] for call in calls]
    assert commands == ["hdiutil", "ditto", "codesign", "hdiutil", "xattr"] + (["open"] if relaunch else [])
    assert calls[0].startswith("hdiutil attach -nobrowse -readonly")
    assert calls[0].endswith(str(mac_app.package))
    assert calls[2].startswith(f"codesign --verify --deep --strict {mac_app.bundle.parent}/.TunnelFlare.app.new-")
    assert calls[3].startswith("hdiutil detach")
    assert calls[4] == f"xattr -dr com.apple.quarantine {mac_app.bundle}"
    if relaunch:
        assert calls[5] == f"open {mac_app.bundle}"
    log = mac_app.log.read_text()
    assert "Mounting the disk image" in log
    assert "Verifying the code signature" in log
    assert log.rstrip().endswith("Update complete")


@posix_only
def test_macos_helper_keeps_old_bundle_on_bad_signature(mac_app, monkeypatch):
    monkeypatch.setenv("STUB_CODESIGN_FAIL", "1")

    with pytest.raises(UpdateError, match="update.log"):
        updater.install(mac_app.package, relaunch=False, block=True)

    assert mac_app.executable.read_text() == "old"
    assert sorted(p.name for p in mac_app.bundle.parent.iterdir()) == ["TunnelFlare.app"]
    assert not any(call.startswith("open") for call in mac_app.calls())
    assert any(call.startswith("hdiutil detach") for call in mac_app.calls())
    assert "ERROR: The new version's code signature is invalid" in mac_app.log.read_text()


@posix_only
def test_macos_helper_waits_for_the_app_to_quit(mac_app):
    running_app = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(60)"])
    try:
        updater.install(mac_app.package, wait_pid=running_app.pid)
        time.sleep(1.0)
        assert mac_app.executable.read_text() == "old"
        assert mac_app.calls() == []
    finally:
        running_app.kill()
        running_app.wait()

    assert wait_for(lambda: mac_app.log.exists() and "Update complete" in mac_app.log.read_text())
    assert mac_app.executable.read_text() == "new"
    assert mac_app.calls()[-1] == f"open {mac_app.bundle}"


# --------------------------------------------------------------------------- Linux AppImage


@pytest.fixture
def appimage(tmp_path, monkeypatch, linux, frozen):
    target = tmp_path / "My Apps" / "TunnelFlare-0.2.1-linux-x86_64.AppImage"
    target.parent.mkdir()
    target.write_text("old")
    monkeypatch.setenv("APPIMAGE", str(target))
    return target


def test_appimage_replaced_without_relaunch(tmp_path, appimage, fake_popen):
    package = tmp_path / LINUX_ASSET
    package.write_bytes(b"new appimage")

    updater.install(package, relaunch=False)

    assert appimage.read_bytes() == b"new appimage"
    assert [p.name for p in appimage.parent.iterdir()] == [appimage.name]
    if POSIX:
        assert stat.S_IMODE(appimage.stat().st_mode) == 0o755
    assert fake_popen == []


@posix_only
def test_appimage_atomic_swap_and_relaunch(tmp_path, appimage, monkeypatch):
    marker = tmp_path / "relaunched"
    monkeypatch.setenv("RELAUNCH_MARKER", str(marker))
    package = tmp_path / LINUX_ASSET
    package.write_text('#!/bin/sh\necho "$APPIMAGE" > "$RELAUNCH_MARKER"\n')
    old_inode = appimage.stat().st_ino
    running_app = subprocess.Popen([PYTHON, "-c", "import time; time.sleep(60)"])
    try:
        with open(appimage) as old_file:
            updater.install(package, wait_pid=running_app.pid)
            assert old_file.read() == "old"  # the running copy keeps its file
        assert appimage.stat().st_ino != old_inode
        assert appimage.read_text() == package.read_text()
        assert stat.S_IMODE(appimage.stat().st_mode) == 0o755
        assert [p.name for p in appimage.parent.iterdir()] == [appimage.name]
        time.sleep(1.0)
        assert not marker.exists()  # the helper waits for the old process
    finally:
        running_app.kill()
        running_app.wait()

    assert wait_for(lambda: marker.exists() and marker.read_text().strip())
    assert marker.read_text().strip() == str(appimage)


# --------------------------------------------------------------------------- CLI


def test_cli_check_prints_json(github, linux, monkeypatch, capsys):
    monkeypatch.delattr(sys, "frozen", raising=False)
    github.publish("v0.3.0", {LINUX_ASSET: b"linux"})

    assert updater.run_cli(["--check"]) == 0

    status = json.loads(capsys.readouterr().out)
    assert status["current"] == "0.2.1"
    assert status["latest"] == "0.3.0"
    assert status["update_available"] is True
    assert status["asset"] == LINUX_ASSET
    assert status["install_supported"] is False
    assert "source" in status["reason"]


def test_cli_install_up_to_date(github, linux, monkeypatch, capsys):
    monkeypatch.setenv("TUNNELFLARE_VERSION_OVERRIDE", "0.3.0")
    github.publish("v0.3.0", {LINUX_ASSET: b"linux"})
    assert updater.run_cli(["--update", "--install"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_cli_install_appimage(github, appimage, capsys):
    github.publish("v0.3.0", {LINUX_ASSET: b"new appimage"})

    assert updater.run_cli(["--install", "--no-relaunch", "--quiet", "--wait"]) == 0

    assert appimage.read_bytes() == b"new appimage"
    assert "installed" in capsys.readouterr().out


def test_cli_install_unsupported(github, linux, monkeypatch, capsys):
    monkeypatch.delattr(sys, "frozen", raising=False)
    github.publish("v0.3.0", {LINUX_ASSET: b"linux"})
    assert updater.run_cli(["--install"]) == 1
    assert "source" in capsys.readouterr().err


def test_cli_install_checksum_failure(github, appimage, capsys):
    github.publish("v0.3.0", {LINUX_ASSET: b"new appimage"}, checksums=f"{'1' * 64}  {LINUX_ASSET}\n")
    assert updater.run_cli(["--install", "--no-relaunch", "--wait"]) == 1
    assert "SHA-256 mismatch" in capsys.readouterr().err
    assert appimage.read_text() == "old"


def test_cli_errors(github, capsys):
    github.publish("v0.3.0", {}, release_status=500, release_body=b"{}")
    assert updater.run_cli(["--check"]) == 1
    assert "Update check failed" in capsys.readouterr().err
    assert updater.run_cli([]) == 1
    assert updater.run_cli(["--check", "--install"]) == 1
