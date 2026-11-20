"""PyInstaller spec for TunnelFlare (all targets, onedir).

Normally driven by packaging/build.py, which prepares the inputs and then runs:

    python -m PyInstaller --noconfirm --clean --workpath build/pyinstaller \
        --distpath dist packaging/tunnelflare.spec -- --target <target>

Parameters reach this spec as follows:
  --target (after "--")    linux-x86_64 | macos-arm64 | macos-x86_64 | windows-x64;
                           selects the cloudflared binary, the license directory
                           and, on macOS, target_arch (arm64 / x86_64).
  version                  __version__ parsed from tunnelflare_backend/__init__.py.
  MACOS_CODESIGN_IDENTITY  env var; macOS signing identity. Unset or empty means
                           PyInstaller's ad-hoc signature.
Inputs produced by build.py (paths relative to the repo root):
  build/cloudflared/<target>/cloudflared[.exe]   (packaging/fetch_cloudflared.py)
  build/icons/tunnelflare.{ico,icns}             (packaging/make_icons.py)
  build/licenses/<target>/                       (packaging/collect_licenses.py)
Output: dist/TunnelFlare/ (onedir) and, on macOS, dist/TunnelFlare.app.
"""

import argparse
import os
import sys

sys.path.insert(0, SPECPATH)
import buildlib

parser = argparse.ArgumentParser(prog="tunnelflare.spec")
parser.add_argument("--target", required=True, choices=sorted(buildlib.TARGETS))
options = parser.parse_args()

TARGET = options.target
IS_WINDOWS = TARGET.startswith("windows")
IS_MACOS = TARGET.startswith("macos")
ROOT = buildlib.ROOT
BUILD = buildlib.BUILD
VERSION = buildlib.app_version()
NAME = buildlib.APP_NAME

CLOUDFLARED = (
    BUILD
    / "cloudflared"
    / TARGET
    / ("cloudflared.exe" if IS_WINDOWS else "cloudflared")
)
LICENSES = BUILD / "licenses" / TARGET
ICON_ICO = buildlib.ICONS / "tunnelflare.ico"
ICON_ICNS = buildlib.ICONS / "tunnelflare.icns"
for required in (
    CLOUDFLARED,
    LICENSES / "THIRD-PARTY-NOTICES.txt",
    ICON_ICO,
    ICON_ICNS,
):
    if not required.exists():
        raise SystemExit(f"missing build input {required}; run packaging/build.py")

version_info = None
if IS_WINDOWS:
    from PyInstaller.utils.win32 import versioninfo as vi

    numbers = tuple(int(part) for part in VERSION.split(".")[:4])
    numbers += (0,) * (4 - len(numbers))
    version_info = vi.VSVersionInfo(
        ffi=vi.FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            vi.StringFileInfo(
                [
                    vi.StringTable(
                        "040904B0",
                        [
                            vi.StringStruct("CompanyName", "madroots"),
                            vi.StringStruct("FileDescription", NAME),
                            vi.StringStruct("FileVersion", VERSION),
                            vi.StringStruct("InternalName", NAME),
                            vi.StringStruct(
                                "LegalCopyright", "TunnelFlare contributors"
                            ),
                            vi.StringStruct("OriginalFilename", f"{NAME}.exe"),
                            vi.StringStruct("ProductName", NAME),
                            vi.StringStruct("ProductVersion", VERSION),
                        ],
                    )
                ]
            ),
            vi.VarFileInfo([vi.VarStruct("Translation", [0x0409, 1200])]),
        ],
    )

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[(str(CLOUDFLARED), ".")],
    datas=[
        (str(ROOT / "tunnelflare_gui" / "resources"), "tunnelflare_gui/resources"),
        (str(LICENSES), "licenses"),
    ],
    hiddenimports=["PySide6.QtSvg"],
    excludes=["tkinter", "_tkinter", "turtle", "turtledemo", "idlelib"],
    noarchive=False,
)
# The fixed Fusion style and palette replace the desktop theme. Qt's GTK3 and
# XDG-portal theme plugins would load the build host's GTK stack on users'
# desktops (version clashes on newer distros), so they are not shipped.
a.binaries = [entry for entry in a.binaries if "platformthemes" not in entry[0].replace("\\", "/").split("/")]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON_ICO) if IS_WINDOWS else str(ICON_ICNS) if IS_MACOS else None,
    version=version_info,
    target_arch={"macos-arm64": "arm64", "macos-x86_64": "x86_64"}.get(TARGET),
    codesign_identity=os.environ.get("MACOS_CODESIGN_IDENTITY") or None,
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=NAME)

if IS_MACOS:
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=str(ICON_ICNS),
        bundle_identifier="io.github.madroots.tunnelflare",
        version=VERSION,
        info_plist={
            "CFBundleName": NAME,
            "CFBundleDisplayName": NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "14.0",
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.developer-tools",
        },
    )
