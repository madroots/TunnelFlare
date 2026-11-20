"""Self-update: find the latest GitHub release, download and verify it, install it.

Standard library only and Qt-free, so it can run in worker threads and from the
command line (`TunnelFlare --update --check | --install`).
"""

import argparse
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tunnelflare_backend import __version__
from tunnelflare_backend.config_manager import default_config_dir
from tunnelflare_backend.net import ssl_context

API_URL = "https://api.github.com/repos/madroots/TunnelFlare/releases/latest"
CHECKSUMS_NAME = "SHA256SUMS.txt"

_CHUNK_SIZE = 64 * 1024
_CHECKSUMS_MAX_BYTES = 1024 * 1024
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_VERSION_RE = re.compile(r"[vV]?(\d+(?:\.\d+)*)")

# Windows process creation flags (constants only exist in subprocess on Windows).
_DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
_CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)

# Runs detached on macOS after the app quits. Paths arrive as positional
# arguments, so no path is ever interpolated into shell code.
_MACOS_HELPER = r"""#!/bin/sh
# TunnelFlare macOS updater: replaces the app bundle with the one in a disk image.
# Usage: update.sh WAIT_PID DMG APP_BUNDLE LOG RELAUNCH(0|1) WORK_DIR
PID=$1
DMG=$2
APP=$3
LOG=$4
RELAUNCH=$5
WORK=$6
MNT="$WORK/mnt"
PARENT=$(dirname "$APP")
NAME=$(basename "$APP")
NEW="$PARENT/.$NAME.new-$$"
OLD="$PARENT/.$NAME.old-$$"
MOUNTED=0

log() {
    printf '%s [helper] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG"
}

detach() {
    if [ "$MOUNTED" = 1 ]; then
        log "Detaching the disk image"
        hdiutil detach "$MNT" -quiet >> "$LOG" 2>&1 \
            || hdiutil detach "$MNT" -force -quiet >> "$LOG" 2>&1 \
            || log "Warning: could not detach $MNT"
        MOUNTED=0
    fi
}

cleanup() {
    detach
    rmdir "$MNT" 2>/dev/null
    rm -f "$WORK/update.sh"
    rmdir "$WORK" 2>/dev/null
}

fail() {
    log "ERROR: $*"
    rm -rf "$NEW"
    cleanup
    if [ "$RELAUNCH" = 1 ] && [ -d "$APP" ]; then
        log "Reopening the current version"
        open "$APP" >> "$LOG" 2>&1
    fi
    log "Update failed"
    exit 1
}

log "Updating $APP from $DMG"
if [ "$PID" != 0 ]; then
    log "Waiting for TunnelFlare (pid $PID) to quit"
    waited=0
    while kill -0 "$PID" 2>/dev/null; do
        if [ "$waited" -ge 120 ]; then
            RELAUNCH=0
            fail "TunnelFlare (pid $PID) did not quit within 60 seconds"
        fi
        sleep 0.5
        waited=$((waited + 1))
    done
fi

mkdir -p "$MNT" || fail "Could not create the mount point $MNT"
log "Mounting the disk image"
hdiutil attach -nobrowse -readonly -noautoopen -mountpoint "$MNT" "$DMG" >> "$LOG" 2>&1 \
    || fail "Could not mount $DMG"
MOUNTED=1

SRC=
for candidate in "$MNT"/*.app; do
    if [ -d "$candidate" ]; then
        SRC=$candidate
        break
    fi
done
[ -n "$SRC" ] || fail "The disk image contains no application"

log "Copying $(basename "$SRC") to $NEW"
rm -rf "$NEW"
ditto "$SRC" "$NEW" >> "$LOG" 2>&1 || fail "Copying the new version failed"

log "Verifying the code signature"
codesign --verify --deep --strict "$NEW" >> "$LOG" 2>&1 \
    || fail "The new version's code signature is invalid"

log "Replacing $APP"
mv "$APP" "$OLD" || fail "Could not move the current version aside"
if ! mv "$NEW" "$APP"; then
    mv "$OLD" "$APP"
    fail "Could not move the new version into place"
fi
rm -rf "$OLD" || log "Warning: could not remove $OLD"

detach

log "Clearing the quarantine attribute"
xattr -dr com.apple.quarantine "$APP" > /dev/null 2>&1 || true

cleanup
if [ "$RELAUNCH" = 1 ]; then
    log "Relaunching TunnelFlare"
    open "$APP" >> "$LOG" 2>&1 || log "Warning: could not relaunch TunnelFlare"
fi
log "Update complete"
exit 0
"""

# Linux relaunch helper (`sh -c`): wait for the old process, then start the new AppImage.
_APPIMAGE_RELAUNCH = r"""pid=$1
app=$2
if [ "$pid" != 0 ]; then
    waited=0
    while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt 120 ]; do
        sleep 0.5
        waited=$((waited + 1))
    done
fi
exec "$app"
"""


class UpdateError(Exception):
    """An update step failed. The message is meant to be shown to users."""


@dataclass(frozen=True)
class Release:
    """The latest published release. asset_* are None when it has no file for this platform."""

    version: str
    page_url: str
    notes: str
    asset_name: str | None
    asset_url: str | None
    asset_size: int | None
    checksums_url: str | None


def current_version():
    """The running app's version; $TUNNELFLARE_VERSION_OVERRIDE wins (tests, CI)."""
    return os.environ.get("TUNNELFLARE_VERSION_OVERRIDE") or __version__


def _parse_version(text):
    match = _VERSION_RE.fullmatch(str(text).strip())
    if not match:
        return None
    parts = [int(part) for part in match.group(1).split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer(candidate, current):
    """True if version `candidate` is newer than `current` (numeric dotted, optional leading v).

    Non-numeric or pre-release versions are never newer.
    """
    new = _parse_version(candidate)
    old = _parse_version(current)
    return new is not None and old is not None and new > old


def _os_name():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def platform_asset_name(version):
    """File name of the release asset this platform installs, or None if there is none."""
    os_name = _os_name()
    if os_name == "windows":
        return f"TunnelFlare-{version}-windows-x64-setup.exe"
    if os_name == "macos":
        return f"TunnelFlare-{version}-macos-universal.dmg"
    if os_name == "linux" and platform.machine().lower() in ("x86_64", "amd64"):
        return f"TunnelFlare-{version}-linux-x86_64.AppImage"
    return None


# --------------------------------------------------------------------------- network


def _api_override():
    return os.environ.get("TUNNELFLARE_UPDATE_API")


def _check_url(url):
    """Only https, unless the API URL was overridden (tests/CI may use a local http server)."""
    allowed = ("http", "https") if _api_override() else ("https",)
    if urllib.parse.urlsplit(url).scheme.lower() not in allowed:
        raise UpdateError(f"Refusing to download over an insecure connection: {url}")


class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_error_message(error, url):
    if error.code in (403, 429) and error.headers.get("X-RateLimit-Remaining") == "0":
        return "GitHub's API rate limit was reached. Try again later."
    return f"The update server answered HTTP {error.code} ({error.reason}) for {url}."


def _open(url, accept, timeout):
    _check_url(url)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"TunnelFlare/{current_version()}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_context()), _RedirectHandler
    )
    host = urllib.parse.urlsplit(url).hostname or url
    try:
        return opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise UpdateError(_http_error_message(exc, url)) from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"Could not connect to {host}: {exc.reason}") from exc
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise UpdateError(f"Could not connect to {host}: {exc}") from exc


def _int_or_none(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _download_url(asset):
    url = asset.get("browser_download_url") if asset else None
    return url if isinstance(url, str) and url else None


def _parse_release(data):
    if not isinstance(data, dict):
        raise UpdateError("The update server sent invalid release information.")
    tag = data.get("tag_name")
    if not isinstance(tag, str) or not tag.strip():
        raise UpdateError("The latest release has no version tag.")
    version = tag.strip()
    if version[0] in "vV":
        version = version[1:]

    assets = {}
    for asset in data.get("assets") or []:
        if isinstance(asset, dict) and isinstance(asset.get("name"), str):
            assets[asset["name"]] = asset

    wanted = platform_asset_name(version)
    asset = assets.get(wanted) if wanted else None
    if not _download_url(asset):
        asset = None
    checksums = assets.get(CHECKSUMS_NAME)
    return Release(
        version=version,
        page_url=str(data.get("html_url") or ""),
        notes=str(data.get("body") or ""),
        asset_name=wanted if asset else None,
        asset_url=_download_url(asset),
        asset_size=_int_or_none(asset.get("size")) if asset else None,
        checksums_url=_download_url(checksums),
    )


def fetch_latest_release(timeout=15):
    """The latest GitHub release (or $TUNNELFLARE_UPDATE_API's answer). Raises UpdateError."""
    url = _api_override() or API_URL
    try:
        with _open(url, "application/vnd.github+json", timeout) as response:
            data = json.load(response)
    except (OSError, http.client.HTTPException) as exc:
        raise UpdateError(f"Could not read the release information: {exc}") from exc
    except ValueError as exc:
        raise UpdateError("The update server sent invalid release information.") from exc
    return _parse_release(data)


def check_for_update(current_version, timeout=15):
    """The latest release if it is newer than `current_version`, else None. Raises UpdateError."""
    release = fetch_latest_release(timeout=timeout)
    return release if is_newer(release.version, current_version) else None


# --------------------------------------------------------------------------- download


def _expected_checksum(release, timeout):
    try:
        with _open(release.checksums_url, "text/plain", timeout) as response:
            text = response.read(_CHECKSUMS_MAX_BYTES).decode("utf-8", "replace")
    except (OSError, http.client.HTTPException) as exc:
        raise UpdateError(f"Could not download {CHECKSUMS_NAME}: {exc}") from exc
    for line in text.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or not _SHA256_RE.fullmatch(fields[0]):
            continue
        if fields[1].strip().lstrip("*") == release.asset_name:
            return fields[0].lower()
    raise UpdateError(
        f"{CHECKSUMS_NAME} lists no checksum for {release.asset_name}, so the download can't be verified."
    )


def _content_length(response):
    try:
        length = int(response.headers.get("Content-Length", ""))
    except ValueError:
        return None
    return length if length >= 0 else None


def download_release(release, dest_dir, progress=None, timeout=30):
    """Download the release's asset into dest_dir and verify it against SHA256SUMS.txt.

    progress(done_bytes, total_bytes) is called as data arrives (total is 0 when
    unknown); an exception raised from it aborts the download. Returns the file path.
    """
    name = release.asset_name
    if not name or not release.asset_url:
        raise UpdateError(f"TunnelFlare {release.version} has no download for this system.")
    if Path(name).name != name or name in (".", ".."):
        raise UpdateError(f"Invalid download name: {name!r}")
    if not release.checksums_url:
        raise UpdateError(
            f"TunnelFlare {release.version} has no {CHECKSUMS_NAME}, so the download can't be verified."
        )
    expected = _expected_checksum(release, timeout)

    dest_dir = Path(dest_dir)
    target = dest_dir / name
    partial = dest_dir / (name + ".part")
    digest = hashlib.sha256()
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        with _open(release.asset_url, "application/octet-stream", timeout) as response:
            total = _content_length(response) or release.asset_size or 0
            done = 0
            with open(partial, "wb") as out:
                if progress:
                    progress(0, total)
                while chunk := response.read(_CHUNK_SIZE):
                    out.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except (OSError, http.client.HTTPException) as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"Downloading {name} failed: {exc}") from exc
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    if digest.hexdigest() != expected:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"The download of {name} is corrupt (SHA-256 mismatch). Please try again.")
    os.replace(partial, target)
    return target


# --------------------------------------------------------------------------- install


def _log_path():
    path = default_config_dir() / "update.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _log(message):
    try:
        with open(_log_path(), "a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        pass


def _dir_writable(path):
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".tunnelflare-write-test-"):
            return True
    except OSError:
        return False


def _mac_bundle():
    return Path(sys.executable).parents[2]


def install_support():
    """(supported, reason): can this copy replace itself? reason is user-facing ("" if supported)."""
    if not getattr(sys, "frozen", False):
        return False, "Automatic updates are only available in the packaged app, not when running from source."

    os_name = _os_name()
    if os_name == "windows":
        app_dir = Path(sys.executable).parent
        if not (app_dir / "unins000.exe").is_file():
            return False, (
                "The portable version of TunnelFlare can't update itself. Download the new version "
                "from the release page, or use the installer to enable automatic updates."
            )
        if not _dir_writable(app_dir):
            return False, (
                f"TunnelFlare was installed for all users in {app_dir}. "
                "Run the new installer as an administrator to update it."
            )
        return True, ""

    if os_name == "macos":
        bundle = _mac_bundle()
        if bundle.suffix != ".app":
            return False, "TunnelFlare is not running from an app bundle, so it can't update itself."
        if "AppTranslocation" in bundle.parts or not _dir_writable(bundle.parent):
            return False, "Move TunnelFlare to the Applications folder to enable automatic updates."
        return True, ""

    if os_name == "linux":
        appimage = os.environ.get("APPIMAGE")
        if not appimage:
            return False, "Automatic updates are only available for the AppImage version of TunnelFlare."
        folder = Path(appimage).parent
        if not _dir_writable(folder):
            return False, f"The folder containing the AppImage ({folder}) is not writable."
        return True, ""

    return False, "Automatic updates are not available on this platform."


def _helper_env():
    """Environment for helper processes, without the frozen app's library path overrides."""
    env = dict(os.environ)
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(var + "_ORIG", None)  # PyInstaller keeps the pre-launch value here
        if original is not None:
            env[var] = original
        elif getattr(sys, "frozen", False):
            env.pop(var, None)
    path = env.get("PATH", "")
    entries = path.split(os.pathsep) if path else []
    for system_dir in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        if system_dir not in entries:
            entries.append(system_dir)
    env["PATH"] = os.pathsep.join(entries)
    return env


def _spawn(cmd, **kwargs):
    kwargs.setdefault("stdout", subprocess.DEVNULL)
    kwargs.setdefault("stderr", subprocess.DEVNULL)
    try:
        return subprocess.Popen(cmd, stdin=subprocess.DEVNULL, close_fds=True, **kwargs)
    except OSError as exc:
        raise UpdateError(f"Could not start the installer: {exc}") from exc


def _install_windows(package, relaunch, show_progress, block):
    install_dir = Path(sys.executable).parent
    cmd = [
        str(package),
        "/SILENT" if show_progress else "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CURRENTUSER",
        "/CLOSEAPPLICATIONS",
        f"/DIR={install_dir}",
    ]
    if relaunch:
        cmd.append("/RELAUNCH=1")
    _log(f"Starting {subprocess.list2cmdline(cmd)}")
    process = _spawn(cmd, creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP)
    if block:
        code = process.wait()
        if code:
            raise UpdateError(f"The installer failed (exit code {code}).")
        _log("Installer finished")


def _install_macos(package, relaunch, wait_pid, block):
    bundle = _mac_bundle()
    log_path = _log_path()
    work = Path(tempfile.mkdtemp(prefix="tunnelflare-update-"))
    script = work / "update.sh"
    script.write_text(_MACOS_HELPER, encoding="utf-8")
    cmd = [
        "/bin/sh",
        str(script),
        str(wait_pid),
        str(package),
        str(bundle),
        str(log_path),
        "1" if relaunch else "0",
        str(work),
    ]
    _log(f"Starting the macOS update helper for {bundle}")
    with open(log_path, "ab") as log:
        process = _spawn(
            cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=_helper_env()
        )
    if block and process.wait():
        raise UpdateError(f"Installing the update failed. See {log_path} for details.")


def _install_appimage(package, relaunch, wait_pid):
    target = Path(os.environ["APPIMAGE"])
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".update", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as out, open(package, "rb") as source:
            shutil.copyfileobj(source, out, 1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(temp_name, 0o755)
        os.replace(temp_name, target)
    except OSError as exc:
        Path(temp_name).unlink(missing_ok=True)
        raise UpdateError(f"Could not replace {target}: {exc}") from exc
    _log(f"Replaced {target}")
    if relaunch:
        _spawn(
            ["/bin/sh", "-c", _APPIMAGE_RELAUNCH, "tunnelflare-relaunch", str(wait_pid), str(target)],
            start_new_session=True,
            env=_helper_env(),
        )
        _log("Relaunch scheduled")


def install(package, relaunch=True, show_progress=True, wait_pid=None, block=False):
    """Install a downloaded, verified package over the running copy.

    Returns as soon as the installer runs; the caller should quit right away so it
    can replace the app. wait_pid is the process the installer waits for before
    replacing files (default: this process; 0 when block=True, since a blocking
    caller can't exit first). block=True waits until installation finishes.
    Raises UpdateError.
    """
    supported, reason = install_support()
    if not supported:
        raise UpdateError(reason)
    package = Path(package).resolve()
    if not package.is_file():
        raise UpdateError(f"The update package {package} does not exist.")
    if wait_pid is None:
        wait_pid = 0 if block else os.getpid()
    _log(f"Installing {package} (relaunch={relaunch}, block={block}, wait_pid={wait_pid})")

    os_name = _os_name()
    if os_name == "windows":
        _install_windows(package, relaunch, show_progress, block)
    elif os_name == "macos":
        _install_macos(package, relaunch, wait_pid, block)
    else:
        _install_appimage(package, relaunch, wait_pid)


# --------------------------------------------------------------------------- CLI


def _print(*args, file=None):
    stream = file or sys.stdout
    if stream is not None:  # windowed frozen builds have no console
        print(*args, file=stream, flush=True)


class _ProgressPrinter:
    def __init__(self, name):
        self.name = name
        self.last = -1

    def __call__(self, done, total):
        if total <= 0:
            return
        percent = min(100, done * 100 // total) // 10 * 10
        if percent != self.last:
            self.last = percent
            _print(f"Downloading {self.name}: {percent}%", file=sys.stderr)


def run_cli(argv):
    """`TunnelFlare --update --check` or `--update --install [--no-relaunch] [--quiet] [--wait]`."""
    argv = list(argv)
    if argv[:1] == ["--update"]:
        argv = argv[1:]
    parser = argparse.ArgumentParser(
        prog="TunnelFlare --update", description="Check for and install TunnelFlare updates."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="print the update status as JSON")
    mode.add_argument("--install", action="store_true", help="download, verify and install the latest release")
    parser.add_argument("--no-relaunch", action="store_true", help="don't start TunnelFlare after installing")
    parser.add_argument("--quiet", action="store_true", help="no progress output or installer window")
    parser.add_argument("--wait", action="store_true", help="wait until the installation has finished")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 1 if exc.code else 0

    current = current_version()
    try:
        release = fetch_latest_release()
    except UpdateError as exc:
        _print(f"Update check failed: {exc}", file=sys.stderr)
        return 1
    available = is_newer(release.version, current)
    supported, reason = install_support()

    if args.check:
        _print(json.dumps({
            "current": current,
            "latest": release.version,
            "update_available": available,
            "asset": release.asset_name,
            "install_supported": supported,
            "reason": reason,
        }, indent=2))
        return 0

    if not available:
        _print(f"TunnelFlare {current} is up to date (latest release: {release.version}).")
        return 0
    if not release.asset_name:
        _print(f"TunnelFlare {release.version} has no download for this system: {release.page_url}",
               file=sys.stderr)
        return 1
    if not supported:
        _print(reason, file=sys.stderr)
        return 1

    dest = tempfile.mkdtemp(prefix="tunnelflare-update-")
    try:
        package = download_release(
            release, dest, progress=None if args.quiet else _ProgressPrinter(release.asset_name)
        )
        if not args.quiet:
            _print(f"Verified {package.name}; installing TunnelFlare {release.version}.")
        install(package, relaunch=not args.no_relaunch, show_progress=not args.quiet, block=args.wait)
    except UpdateError as exc:
        shutil.rmtree(dest, ignore_errors=True)
        _print(f"Update failed: {exc}", file=sys.stderr)
        return 1
    if args.wait:
        shutil.rmtree(dest, ignore_errors=True)
        _print(f"TunnelFlare {release.version} is installed.")
    else:
        _print(f"The TunnelFlare {release.version} installer is running.")
    return 0
