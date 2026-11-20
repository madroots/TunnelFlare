"""Build TunnelFlare release artifacts for one target on its native host.

Usage: python packaging/build.py --target {linux-x86_64,macos-universal,windows-x64}

Steps: fetch cloudflared -> (macos-universal: universal2 psutil wheel, see
universal2.py) -> render icons -> collect licenses -> PyInstaller
(packaging/tunnelflare.spec) -> verify bundle contents (Qt plugins, and on
macOS that every Mach-O file has arm64 + x86_64) -> package into dist/release/
-> write dist/release/build-info.json.

Environment:
  MACOS_CODESIGN_IDENTITY  macOS signing identity passed to the spec (default: ad-hoc).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import buildlib
import collect_licenses
import fetch_cloudflared
import universal2
from buildlib import BUILD, DIST, ICONS, PACKAGING, RELEASE, ROOT, run

APPIMAGETOOL_URL = "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage"
APPIMAGETOOL_SHA256 = "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
# appimagetool would otherwise fetch the unpinned "continuous" runtime at build time.
RUNTIME_URL = "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64"
RUNTIME_SHA256 = "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
UPDATE_INFO = "gh-releases-zsync|madroots|TunnelFlare|latest|TunnelFlare-*-linux-x86_64.AppImage.zsync"
ISCC_DEFAULT = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")


def bundle_layout(target: str) -> tuple[Path, Path, Path]:
    """Return (bundle root, executable, sys._MEIPASS directory) of the PyInstaller output."""
    name = buildlib.APP_NAME
    if target.startswith("macos"):
        contents = DIST / f"{name}.app" / "Contents"
        return DIST / f"{name}.app", contents / "MacOS" / name, contents / "Frameworks"
    exe = name + (".exe" if target.startswith("windows") else "")
    return DIST / name, DIST / name / exe, DIST / name / "_internal"


def verify_universal(root: Path, exe: Path, meipass: Path, files: list[Path]) -> list[str]:
    """Problems unless every Mach-O file in the app has both arm64 and x86_64."""
    problems = [
        f"{p.relative_to(root)} is not universal2: {' '.join(sorted(archs))}"
        for p in files
        if (archs := buildlib.macho_file_archs(p)) is not None
        and not buildlib.UNIVERSAL_ARCHS <= archs
    ]
    python_lib = meipass / "Python"
    if not python_lib.exists():
        python_lib = next(iter(sorted(meipass.glob("libpython3*.dylib"))), python_lib)
    key_files = {
        "executable": exe,
        "cloudflared": meipass / "cloudflared",
        "Python": python_lib,
        "QtCore": meipass / "PySide6/Qt/lib/QtCore.framework/Versions/A/QtCore",
        **{f"psutil/{p.name}": p for p in sorted((meipass / "psutil").glob("*.so"))},
    }
    if not any(name.startswith("psutil/") for name in key_files):
        problems.append("no psutil extension module in the bundle")
    for name, path in key_files.items():
        if not path.exists():
            problems.append(f"{name}: {path} missing")
            continue
        archs = subprocess.run(
            ["lipo", "-archs", str(path)], capture_output=True, text=True, check=True
        ).stdout.split()
        print(f"  lipo -archs {name}: {' '.join(archs)}")
        if not buildlib.UNIVERSAL_ARCHS <= set(archs):
            problems.append(f"{name} is not universal2: {' '.join(archs)}")
    return problems


def verify_bundle(target: str, cloudflared_version: str) -> Path:
    root, exe, meipass = bundle_layout(target)
    family = buildlib.family(target)
    problems = []

    def need(path: Path, what: str) -> None:
        if not path.exists():
            problems.append(f"{what}: {path} missing")

    need(exe, "executable")
    cloudflared = meipass / (
        "cloudflared.exe" if family == "windows" else "cloudflared"
    )
    need(cloudflared, "cloudflared")
    for rel in (
        "tray.svg",
        "fonts/Inter-Regular.ttf",
        "fonts/Inter-OFL.txt",
        "fonts/JetBrainsMono-OFL.txt",
    ):
        need(meipass / "tunnelflare_gui" / "resources" / rel, "resource")
    for rel in (
        "THIRD-PARTY-NOTICES.txt",
        "Python",
        "PySide6-Essentials",
        "cloudflared/LICENSE",
    ):
        need(meipass / "licenses" / rel, "license")

    search = root / "Contents" if family == "macos" else meipass
    # Real files only: macOS bundles link data files and frameworks with symlinks.
    files = [p for p in search.rglob("*") if p.is_file() and not p.is_symlink()]
    plugins = {
        p.relative_to(search).as_posix(): plugin
        for p in files
        if (plugin := buildlib.qt_plugin(p.relative_to(search).as_posix()))
    }
    for path, plugin in sorted(plugins.items()):
        if not buildlib.qt_plugin_wanted(target, plugin):
            problems.append(f"unwanted Qt plugin bundled: {path}")
    for plugin_dir, names in buildlib.QT_PLUGINS[family].items():
        for name in names or ():
            if (plugin_dir, name) not in plugins.values():
                problems.append(f"Qt plugin {plugin_dir}/{name} not bundled")
    if any(p.suffix == ".qm" for p in files):
        problems.append("Qt translations (.qm) bundled")
    if family == "linux" and not any(p.name == "libxcb-cursor.so.0" for p in files):
        problems.append(
            "libxcb-cursor.so.0 was not bundled; Qt's xcb platform plugin needs it. "
            "Install it on the build host (Debian/Ubuntu: apt install libxcb-cursor0) and rebuild."
        )
    if family == "macos":
        problems += verify_universal(root, exe, meipass, files)
    if problems:
        raise SystemExit("bundle verification failed:\n  " + "\n  ".join(problems))

    if not target.startswith("windows") and not os.access(cloudflared, os.X_OK):
        raise SystemExit(f"{cloudflared} is not executable")
    output = subprocess.run(
        [str(cloudflared), "--version"], capture_output=True, text=True, check=True
    ).stdout
    if cloudflared_version not in output:
        raise SystemExit(
            f"bundled cloudflared reports {output.strip()!r}, expected {cloudflared_version}"
        )

    size = sum(p.stat().st_size for p in files)
    print(f"bundle OK: {root} ({size / 2**20:.1f} MiB, {len(files)} files)")
    print("  Qt plugins: " + ", ".join(sorted(plugins)))
    print("  cloudflared: " + output.strip())
    return exe


def package_linux(version: str) -> dict:
    name = buildlib.APP_NAME
    appdir = BUILD / "AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    shutil.copytree(DIST / name, appdir / "usr" / "lib" / name, symlinks=True)
    shutil.copy2(PACKAGING / "linux" / "AppRun", appdir / "AppRun")
    (appdir / "AppRun").chmod(0o755)
    desktop = PACKAGING / "linux" / "tunnelflare.desktop"
    shutil.copy2(desktop, appdir / "tunnelflare.desktop")
    (appdir / "usr" / "share" / "applications").mkdir(parents=True)
    shutil.copy2(
        desktop, appdir / "usr" / "share" / "applications" / "tunnelflare.desktop"
    )
    shutil.copy2(ICONS / "tunnelflare.png", appdir / "tunnelflare.png")
    (appdir / ".DirIcon").symlink_to("tunnelflare.png")
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        icon_dir = (
            appdir / "usr" / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps"
        )
        icon_dir.mkdir(parents=True)
        shutil.copy2(
            ICONS / "png" / f"tunnelflare-{size}.png", icon_dir / "tunnelflare.png"
        )

    tool = buildlib.download(
        APPIMAGETOOL_URL,
        buildlib.CACHE / "appimagetool-1.9.1-x86_64.AppImage",
        APPIMAGETOOL_SHA256,
    )
    tool.chmod(0o755)
    runtime = buildlib.download(
        RUNTIME_URL, buildlib.CACHE / "type2-runtime-20251108-x86_64", RUNTIME_SHA256
    )
    out = RELEASE / f"{name}-{version}-linux-x86_64.AppImage"
    env = dict(os.environ, APPIMAGE_EXTRACT_AND_RUN="1", ARCH="x86_64", VERSION=version)
    # appimagetool bundles zsyncmake and runs it in its working directory, so run it in dist/release.
    run(
        [tool, "--runtime-file", runtime, "-u", UPDATE_INFO, appdir, out],
        env=env,
        cwd=RELEASE,
    )
    artifacts = {"appimage": buildlib.rel(out)}
    zsync = out.with_name(out.name + ".zsync")
    if zsync.exists():
        artifacts["zsync"] = buildlib.rel(zsync)
    else:
        print(
            "WARNING: appimagetool wrote no .zsync file; delta updates will not work",
            flush=True,
        )
    return artifacts


def package_macos(target: str, version: str) -> dict:
    name = buildlib.APP_NAME
    app = DIST / f"{name}.app"
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", app])
    staging = BUILD / "dmg"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    run(["ditto", app, staging / app.name])
    (staging / "Applications").symlink_to("/Applications")
    dmg = RELEASE / f"{name}-{version}-macos-{target.split('-', 1)[1]}.dmg"
    cmd = [
        "hdiutil",
        "create",
        "-volname",
        name,
        "-srcfolder",
        staging,
        "-ov",
        "-format",
        "UDZO",
        dmg,
    ]
    for attempt in range(
        1, 4
    ):  # hdiutil intermittently fails with "Resource busy" on CI runners
        try:
            run(cmd)
            break
        except subprocess.CalledProcessError:
            if attempt == 3:
                raise
            time.sleep(10)
    return {"dmg": buildlib.rel(dmg)}


def package_windows(version: str) -> dict:
    name = buildlib.APP_NAME
    iscc = shutil.which("ISCC") or (
        str(ISCC_DEFAULT) if ISCC_DEFAULT.exists() else None
    )
    if not iscc:
        raise SystemExit(
            f"ISCC.exe (Inno Setup 6) not found on PATH or at {ISCC_DEFAULT}"
        )
    run(
        [
            iscc,
            f"/DAppVersion={version}",
            f"/DSourceDir={DIST / name}",
            f"/DOutputDir={RELEASE}",
            f"/DIconFile={ICONS / 'tunnelflare.ico'}",
            PACKAGING / "windows" / "tunnelflare.iss",
        ]
    )
    setup = RELEASE / f"{name}-{version}-windows-x64-setup.exe"
    if not setup.exists():
        raise SystemExit(f"ISCC did not produce {setup}")
    portable = shutil.make_archive(
        str(RELEASE / f"{name}-{version}-windows-x64-portable"),
        "zip",
        root_dir=DIST,
        base_dir=name,
    )
    return {"setup": buildlib.rel(setup), "portable": buildlib.rel(Path(portable))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, choices=sorted(buildlib.TARGETS))
    target = parser.parse_args().target
    buildlib.check_host(target)
    version = buildlib.app_version()
    cloudflared_version = buildlib.cloudflared_pin()["version"]
    print(
        f"== TunnelFlare {version} for {target} (cloudflared {cloudflared_version})",
        flush=True,
    )

    print("== cloudflared", flush=True)
    print(fetch_cloudflared.fetch(target, BUILD / "cloudflared" / target))
    if target == "macos-universal":
        print("== universal2 wheels", flush=True)
        universal2.ensure_universal_wheels()
    print("== icons", flush=True)
    run([sys.executable, PACKAGING / "make_icons.py", "--out", ICONS])
    print("== licenses", flush=True)
    print(collect_licenses.collect(target, BUILD / "licenses" / target))

    print("== PyInstaller", flush=True)
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--workpath",
            BUILD / "pyinstaller",
            "--distpath",
            DIST,
            PACKAGING / "tunnelflare.spec",
            "--",
            "--target",
            target,
        ],
        cwd=ROOT,
    )
    print("== verify bundle", flush=True)
    exe = verify_bundle(target, cloudflared_version)

    print("== package", flush=True)
    if RELEASE.exists():
        shutil.rmtree(RELEASE)
    RELEASE.mkdir(parents=True)
    if target == "linux-x86_64":
        artifacts = package_linux(version)
    elif target.startswith("macos"):
        artifacts = package_macos(target, version)
    else:
        artifacts = package_windows(version)

    info = {
        "version": version,
        "target": target,
        "cloudflared": cloudflared_version,
        "executable": buildlib.rel(exe),
        "artifacts": artifacts,
    }
    (RELEASE / "build-info.json").write_text(
        json.dumps(info, indent=2) + "\n", encoding="utf-8"
    )
    for path in artifacts.values():
        print(f"  {path}  {(ROOT / path).stat().st_size / 2**20:.1f} MiB")
    print(f"wrote {buildlib.rel(RELEASE / 'build-info.json')}")


if __name__ == "__main__":
    main()
