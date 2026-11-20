"""PyInstaller spec for TunnelFlare (all targets, onedir).

Normally driven by packaging/build.py, which prepares the inputs and then runs:

    python -m PyInstaller --noconfirm --clean --workpath build/pyinstaller \
        --distpath dist packaging/tunnelflare.spec -- --target <target>

Parameters reach this spec as follows:
  --target (after "--")    linux-x86_64 | macos-universal | windows-x64;
                           selects the cloudflared binary, the license directory,
                           the Qt plugins (buildlib.QT_PLUGINS) and, on macOS,
                           target_arch universal2.
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

# Libraries collected for features the app never uses: Qt's software OpenGL
# fallback and the OpenSSL copy Qt's TLS plugin would load on Windows (Python's
# ssl module links its own libssl-3.dll). Dropped unless a kept binary links them.
UNUSED_LIBRARIES = {"opengl32sw.dll", "libssl-3-x64.dll", "libcrypto-3-x64.dll"}


def prune(binaries, datas):
    """Drop unwanted Qt plugins (buildlib.QT_PLUGINS), the libraries only they or
    UNUSED_LIBRARIES pull in (GTK for the platform themes, EGLFS support, ...), the
    symlinks to dropped files, and Qt's translations (no QTranslator is installed)."""
    from PyInstaller.depend.bindepend import get_imports

    def norm(path):
        return os.path.normcase(os.path.realpath(path))

    def base(name):
        name = os.path.basename(name.replace("\\", "/"))
        return name.lower() if IS_WINDOWS else name

    by_path = {norm(entry[1]): entry for entry in binaries}
    by_name = {}
    for entry in binaries:
        by_name.setdefault(base(entry[0]), entry)
        by_name.setdefault(base(entry[1]), entry)
    search_paths = sorted({os.path.dirname(entry[1]) for entry in binaries})
    graph = {}
    for entry in binaries:
        deps = set()
        for name, path in get_imports(entry[1], search_paths):
            dep = by_path.get(norm(path)) if path else None
            dep = dep or by_name.get(base(name))
            if dep and dep != entry:
                deps.add(dep)
        graph[entry] = deps

    def reachable(start):
        seen, stack = set(), list(start)
        while stack:
            for dep in graph[stack.pop()] - seen:
                seen.add(dep)
                stack.append(dep)
        return seen

    dropped = {
        entry
        for entry in binaries
        if (plugin := buildlib.qt_plugin(entry[0]))
        and not buildlib.qt_plugin_wanted(TARGET, plugin)
    }
    unused = {entry for entry in binaries if base(entry[0]) in UNUSED_LIBRARIES}
    candidates = (reachable(dropped) | unused) - dropped
    roots = set(binaries) - dropped - candidates
    removed = dropped | (candidates - reachable(roots))
    removed_dests = {entry[0].replace("\\", "/") for entry in removed}

    def keep_data(entry):
        dest, src, kind = entry
        parts = dest.replace("\\", "/").split("/")
        if parts[0] == "PySide6" and "translations" in parts[:3]:
            return False
        return not (kind == "SYMLINK" and src.replace("\\", "/") in removed_dests)

    kept_datas = [entry for entry in datas if keep_data(entry)]
    size = sum(os.path.getsize(entry[1]) for entry in removed)
    print(
        f"pruned {len(removed)} binaries ({size / 2**20:.1f} MiB) and "
        f"{len(datas) - len(kept_datas)} data files:",
        flush=True,
    )
    for dest in sorted(removed_dests):
        print(f"  - {dest}", flush=True)
    return [entry for entry in binaries if entry not in removed], kept_datas


a.binaries, a.datas = prune(a.binaries, a.datas)
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
    target_arch="universal2" if IS_MACOS else None,
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
