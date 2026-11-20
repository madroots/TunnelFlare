"""Smoke-test the final release artifacts listed in dist/release/build-info.json.

Usage: python packaging/smoke_test.py --target T [--e2e] [--e2e-attempts N]

Installs/unpacks each artifact the way a user would and runs the frozen app's
self-test:
  linux    AppImage with APPIMAGE_EXTRACT_AND_RUN=1 (under `xvfb-run -a` when no display)
  macos    DMG attached read-only, .app copied out with ditto, codesign-verified, run
           natively on the host architecture (the universal DMG is tested on arm64
           and x86_64 runners)
  windows  setup.exe silent per-user install (asserts it does not start the app)
           -> self-test -> reinstall with /RELAUNCH=1 (asserts it starts the app)
           -> silent uninstall (asserts removal); portable zip unpacked -> self-test
           (never --e2e)
Reports: dist/release/selftest-<target>[-<variant>].json; screenshot:
dist/release/screenshot-<target>[-<variant>].png (macOS variant: host architecture).
Exits non-zero if any check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

import buildlib
from buildlib import RELEASE, ROOT, run

SELFTEST_TIMEOUT = 120
E2E_TIMEOUT = 300


def selftest(
    cmd: list,
    target: str,
    variant: str | None,
    expect: str,
    e2e: bool,
    attempts: int,
    screenshot: bool = True,
    env: dict | None = None,
) -> bool:
    suffix = f"-{variant}" if variant else ""
    report = RELEASE / f"selftest-{target}{suffix}.json"
    args = ["--self-test", "--report", report, "--expect-cloudflared", expect]
    if screenshot:
        args += ["--screenshot", RELEASE / f"screenshot-{target}{suffix}.png"]
    if e2e:
        args.append("--e2e")
    tries = attempts if e2e else 1
    for attempt in range(1, tries + 1):
        print(f"== self-test {target}{suffix} (attempt {attempt}/{tries})", flush=True)
        report.unlink(missing_ok=True)
        try:
            code = subprocess.run(
                [str(c) for c in cmd + args],
                check=False,
                env=env,
                timeout=E2E_TIMEOUT if e2e else SELFTEST_TIMEOUT,
            ).returncode
        except subprocess.TimeoutExpired:
            print("self-test timed out", flush=True)
            code = None
        data = None
        if report.exists():
            text = report.read_text(encoding="utf-8")
            print(text, flush=True)
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                print("report is not valid JSON", flush=True)
        else:
            print(f"no report written at {report}", flush=True)
        if code == 0 and isinstance(data, dict) and data.get("ok") is True:
            print(f"self-test {target}{suffix}: PASS", flush=True)
            return True
        print(f"self-test {target}{suffix}: FAIL (exit code {code})", flush=True)
        if attempt < tries:
            time.sleep(10)
    return False


def smoke_linux(info: dict, expect: str, e2e: bool, attempts: int) -> bool:
    appimage = ROOT / info["artifacts"]["appimage"]
    appimage.chmod(0o755)
    cmd = [appimage]
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        xvfb = shutil.which("xvfb-run")
        if xvfb:
            cmd = [xvfb, "-a", "-s", "-screen 0 1280x1024x24", *cmd]
        else:
            print(
                "WARNING: no DISPLAY/WAYLAND_DISPLAY and xvfb-run not found", flush=True
            )
    env = dict(os.environ, APPIMAGE_EXTRACT_AND_RUN="1")
    return selftest(cmd, info["target"], None, expect, e2e, attempts, env=env)


def smoke_macos(info: dict, expect: str, e2e: bool, attempts: int, tmp: Path) -> bool:
    dmg = ROOT / info["artifacts"]["dmg"]
    mount = tmp / "mnt"
    mount.mkdir()
    app = tmp / f"{buildlib.APP_NAME}.app"
    run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", mount, dmg])
    try:
        if not (mount / "Applications").is_symlink():
            raise SystemExit("DMG lacks the /Applications symlink")
        run(["ditto", mount / app.name, app])
    finally:
        run(["hdiutil", "detach", mount, "-force"])
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app])
    exe = app / "Contents" / "MacOS" / buildlib.APP_NAME
    arch = platform.machine()
    run(["lipo", "-archs", exe])
    return selftest([exe], info["target"], arch, expect, e2e, attempts)


def app_processes(exe_name: str) -> int:
    """Number of running processes with this image name (Windows)."""
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sum(line.startswith(f'"{exe_name}"') for line in out.splitlines())


def wait_for_processes(exe_name: str, running: bool, seconds: float) -> bool:
    """Poll until the app is (not) running; True once the state is reached."""
    deadline = time.monotonic() + seconds
    while True:
        if (app_processes(exe_name) > 0) == running:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(1)


def smoke_windows(info: dict, expect: str, e2e: bool, attempts: int, tmp: Path) -> bool:
    target, exe_name = info["target"], f"{buildlib.APP_NAME}.exe"
    setup = ROOT / info["artifacts"]["setup"]
    install = tmp / "installed"
    install_args = [
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/CURRENTUSER",
        f"/DIR={install}",
    ]
    run([setup, *install_args, f"/LOG={tmp / 'setup.log'}"])
    exe, uninstaller = install / exe_name, install / "unins000.exe"
    for path in (exe, uninstaller, install / "_internal"):
        if not path.exists():
            raise SystemExit(f"installer did not create {path}")
    # A plain silent install must not start the app (only /RELAUNCH=1 does).
    time.sleep(5)
    quiet_ok = app_processes(exe_name) == 0
    print(
        f"silent install without /RELAUNCH: {'PASS, app not started' if quiet_ok else 'FAIL, app started'}",
        flush=True,
    )
    if not quiet_ok:
        run(["taskkill", "/F", "/T", "/IM", exe_name])
        wait_for_processes(exe_name, False, 30)
    installed_ok = selftest([exe], target, "installer", expect, e2e, attempts)

    # The in-app updater reinstalls with /RELAUNCH=1 and expects the app to come back.
    run([setup, *install_args, "/RELAUNCH=1", f"/LOG={tmp / 'setup-relaunch.log'}"])
    relaunch_ok = wait_for_processes(exe_name, True, 60)
    print(
        f"silent install with /RELAUNCH=1: {'PASS, app started' if relaunch_ok else 'FAIL, app not started'}",
        flush=True,
    )
    if relaunch_ok:
        run(["taskkill", "/F", "/T", "/IM", exe_name])
        if not wait_for_processes(exe_name, False, 30):
            raise SystemExit(f"{exe_name} is still running after taskkill")

    run([uninstaller, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
    leftovers = [exe, uninstaller, install / "_internal"]
    deadline = (
        time.monotonic() + 120
    )  # the uninstaller re-launches itself from %TEMP% and returns early
    while any(p.exists() for p in leftovers) and time.monotonic() < deadline:
        time.sleep(2)
    remaining = [str(p) for p in leftovers if p.exists()]
    uninstall_ok = not remaining
    print(
        f"uninstall: {'PASS' if uninstall_ok else 'FAIL, left ' + ', '.join(remaining)}",
        flush=True,
    )

    portable = tmp / "portable"
    with zipfile.ZipFile(ROOT / info["artifacts"]["portable"]) as archive:
        archive.extractall(portable)
    portable_ok = selftest(
        [portable / buildlib.APP_NAME / exe_name],
        target,
        "portable",
        expect,
        False,
        1,
        screenshot=False,
    )
    return quiet_ok and installed_ok and relaunch_ok and uninstall_ok and portable_ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, choices=sorted(buildlib.TARGETS))
    parser.add_argument(
        "--e2e", action="store_true", help="also open a real Cloudflare quick tunnel"
    )
    parser.add_argument("--e2e-attempts", type=int, default=3, metavar="N")
    args = parser.parse_args()

    info = json.loads((RELEASE / "build-info.json").read_text(encoding="utf-8"))
    if info["target"] != args.target:
        raise SystemExit(f"build-info.json is for {info['target']}, not {args.target}")
    expect = buildlib.cloudflared_pin()["version"]
    attempts = max(1, args.e2e_attempts)
    tmp = Path(tempfile.mkdtemp(prefix="tunnelflare-smoke-"))
    try:
        if args.target.startswith("linux"):
            ok = smoke_linux(info, expect, args.e2e, attempts)
        elif args.target.startswith("macos"):
            ok = smoke_macos(info, expect, args.e2e, attempts, tmp)
        else:
            ok = smoke_windows(info, expect, args.e2e, attempts, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"== smoke test {args.target}: {'PASS' if ok else 'FAIL'}", flush=True)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
