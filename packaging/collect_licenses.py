"""Collect third-party license texts for the bundle.

Usage: python packaging/collect_licenses.py --target linux-x86_64 [--out build/licenses/<target>]

Run with the build interpreter: Python's own LICENSE comes from sys.base_prefix
and Python package licenses from the installed dist-info (importlib.metadata).
PySide6/shiboken6 wheels ship no license files, so the LGPL/GPL texts from the
pyside-setup v6.12.0 tag are vendored in packaging/licenses/pyside6/.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

import buildlib

LICENSE_PREFIXES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "COPYRIGHT")

QT_NOTICE = """\
Qt for Python (PySide6, shiboken6) and the Qt 6 libraries bundled with it are
used under the GNU Lesser General Public License v3.0 (LGPL-3.0-only); the
license texts are in PySide6-Essentials/ and shiboken6/ (LGPL-3.0 supplements
GPL-3.0, so both texts are included).

Qt and Qt for Python are shipped unmodified as separate, dynamically loaded
shared libraries (libQt6*.so / QtCore.framework / Qt6*.dll and the PySide6
extension modules) inside this application's bundle. You may replace them with
your own compatible builds; the application loads whatever copies sit in its
bundle directory.

The complete corresponding source code is available from:
  Qt for Python {pyside_version}: https://download.qt.io/official_releases/QtForPython/
  Qt 6.12: https://download.qt.io/official_releases/qt/6.12/
Qt contains third-party components under their own licenses; see
https://doc.qt.io/qt-6/licenses-used-in-qt.html.
"""


def python_license() -> Path:
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    base = Path(sys.base_prefix)
    for candidate in (
        base / "LICENSE.txt",
        base / "LICENSE",
        stdlib / "LICENSE.txt",
        stdlib / "LICENSE",
    ):
        if candidate.is_file():
            return candidate
    raise SystemExit(f"Python LICENSE not found under {base} or {stdlib}")


def dist_license_files(dist: metadata.Distribution) -> list[Path]:
    found = []
    for file in dist.files or ():
        parts = file.parts
        in_dist_info = any(p.endswith(".dist-info") for p in parts[:-1])
        if in_dist_info and (
            "licenses" in parts[:-1] or file.name.upper().startswith(LICENSE_PREFIXES)
        ):
            found.append(Path(file.locate()))
    return found


def copy_dist(
    name: str, out: Path, vendored: Path | None = None
) -> metadata.Distribution:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError as exc:
        raise SystemExit(f"{name} is not installed in the build environment") from exc
    files = dist_license_files(dist) or (sorted(vendored.iterdir()) if vendored else [])
    if not files:
        raise SystemExit(f"no license files found for {name}")
    dest = out / name
    dest.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copy2(path, dest / path.name)
    return dist


def collect(target: str, out: Path) -> Path:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    pin = buildlib.cloudflared_pin()
    vendored_qt = buildlib.PACKAGING / "licenses" / "pyside6"

    (out / "Python").mkdir()
    shutil.copy2(python_license(), out / "Python" / "LICENSE.txt")

    rows = [
        (
            "Python",
            platform.python_version(),
            "PSF-2.0",
            "https://www.python.org/downloads/source/",
            "Python/",
        ),
    ]
    dists = [
        (
            "PySide6-Essentials",
            vendored_qt,
            "LGPL-3.0-only",
            "https://download.qt.io/official_releases/QtForPython/",
        ),
        (
            "shiboken6",
            vendored_qt,
            "LGPL-3.0-only",
            "https://download.qt.io/official_releases/QtForPython/",
        ),
        ("psutil", None, "BSD-3-Clause", "https://github.com/giampaolo/psutil"),
        (
            "qrcode",
            None,
            "BSD-3-Clause",
            "https://github.com/lincolnloop/python-qrcode",
        ),
        (
            "PyInstaller",
            None,
            "GPL-2.0-or-later WITH bootloader exception",
            "https://github.com/pyinstaller/pyinstaller",
        ),
    ]
    if target.startswith("windows"):
        dists.append(
            ("colorama", None, "BSD-3-Clause", "https://github.com/tartley/colorama")
        )
    pyside_version = "?"
    for name, vendored, spdx, url in dists:
        dist = copy_dist(name, out, vendored)
        if name == "PySide6-Essentials":
            pyside_version = dist.version
        rows.append((name, dist.version, spdx, url, f"{name}/"))
    rows.append(
        (
            "Qt",
            pyside_version,
            "LGPL-3.0-only",
            "https://download.qt.io/official_releases/qt/6.12/",
            "PySide6-Essentials/",
        )
    )

    version = pin["version"]
    cf_license = buildlib.download(
        pin["license_url"].format(version=version),
        buildlib.CACHE / "cloudflared" / version / "LICENSE",
    )
    (out / "cloudflared").mkdir()
    shutil.copy2(cf_license, out / "cloudflared" / "LICENSE")
    rows.append(
        (
            "cloudflared",
            version,
            "Apache-2.0",
            f"https://github.com/cloudflare/cloudflared/tree/{version}",
            "cloudflared/",
        )
    )
    fonts = "tunnelflare_gui/resources/fonts/"
    rows.append(
        (
            "Inter",
            "-",
            "OFL-1.1",
            "https://github.com/rsms/inter",
            fonts + "Inter-OFL.txt",
        )
    )
    rows.append(
        (
            "JetBrains Mono",
            "-",
            "OFL-1.1",
            "https://github.com/JetBrains/JetBrainsMono",
            fonts + "JetBrainsMono-OFL.txt",
        )
    )
    if target.startswith("linux"):
        rows.append(
            (
                "xcb-util-cursor (libxcb-cursor)",
                "system",
                "MIT",
                "https://gitlab.freedesktop.org/xorg/lib/libxcb-cursor",
                "-",
            )
        )

    header = ("Component", "Version", "License", "Source", "License text")
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header))]

    def fmt(row):
        return "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip()

    lines = [
        f"TunnelFlare {buildlib.app_version()} ({target}) - third-party notices",
        "",
        "TunnelFlare bundles the components below. License texts are in this",
        "directory (paths relative to it); font licenses ship next to the fonts in",
        "the application resources.",
        "",
        fmt(header),
        fmt(tuple("-" * w for w in widths)),
        *(fmt(r) for r in rows),
        "",
        QT_NOTICE.format(pyside_version=pyside_version),
        "cloudflared is Cloudflare's unmodified release binary, downloaded from",
        f"https://github.com/cloudflare/cloudflared/releases/tag/{version} and verified by sha256.",
        "",
    ]
    (out / "THIRD-PARTY-NOTICES.txt").write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", required=True, choices=sorted(buildlib.TARGETS))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    out = (args.out or buildlib.BUILD / "licenses" / args.target).resolve()
    print(collect(args.target, out))


if __name__ == "__main__":
    main()
