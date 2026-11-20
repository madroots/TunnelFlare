"""Shared helpers for the TunnelFlare packaging scripts (stdlib only)."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import time
import urllib.request
from pathlib import Path

PACKAGING = Path(__file__).resolve().parent
ROOT = PACKAGING.parent
BUILD = ROOT / "build"
CACHE = BUILD / "cache"
DIST = ROOT / "dist"
RELEASE = DIST / "release"
ICONS = BUILD / "icons"

APP_NAME = "TunnelFlare"

# Build targets -> (sys.platform prefix, accepted platform.machine() values).
# macos-universal is one universal2 (arm64 + x86_64) app; it needs a universal2 Python.
TARGETS = {
    "linux-x86_64": ("linux", {"x86_64", "amd64"}),
    "macos-universal": ("darwin", {"arm64", "x86_64"}),
    "windows-x64": ("win32", {"amd64", "x86_64"}),
}

# Qt plugins shipped per OS family: plugin dir -> plugin names (file name without
# "lib" prefix and extension), or None for every plugin in that dir. All other
# plugins (styles, tls, networkinformation, platformthemes, generic,
# egldeviceintegrations, other image formats, ...) stay out of the bundle, along
# with the libraries only they need (see tunnelflare.spec).
_SVG_PLUGINS = {"imageformats": {"qsvg"}, "iconengines": {"qsvgicon"}}
QT_PLUGINS = {
    "linux": {
        "platforms": {"qxcb", "qwayland", "qoffscreen"},
        "platforminputcontexts": None,
        "xcbglintegrations": None,
        "wayland-decoration-client": None,
        "wayland-graphics-integration-client": None,
        "wayland-shell-integration": None,
        **_SVG_PLUGINS,
    },
    "macos": {"platforms": {"qcocoa", "qoffscreen"}, **_SVG_PLUGINS},
    "windows": {"platforms": {"qwindows", "qoffscreen"}, **_SVG_PLUGINS},
}


def family(target: str) -> str:
    """OS family of a target: linux, macos or windows."""
    return target.split("-", 1)[0]


def qt_plugin(path: str) -> tuple[str, str] | None:
    """(plugin dir, plugin name) when path is a PySide6 Qt plugin file, else None."""
    parts = path.replace("\\", "/").split("/")
    if "PySide6" not in parts or "plugins" not in parts:
        return None
    index = parts.index("plugins")
    if index < parts.index("PySide6") or len(parts) != index + 3:
        return None
    name = parts[-1].split(".", 1)[0]
    return parts[index + 1], name.removeprefix("lib")


def qt_plugin_wanted(target: str, plugin: tuple[str, str]) -> bool:
    plugin_dir, name = plugin
    keep = QT_PLUGINS[family(target)]
    return plugin_dir in keep and (keep[plugin_dir] is None or name in keep[plugin_dir])


def app_version() -> str:
    """Read __version__ from tunnelflare_backend/__init__.py without importing it."""
    source = (ROOT / "tunnelflare_backend" / "__init__.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise SystemExit("__version__ not found in tunnelflare_backend/__init__.py")


def cloudflared_pin() -> dict:
    return json.loads((PACKAGING / "cloudflared.json").read_text(encoding="utf-8"))


def check_host(target: str) -> None:
    """Refuse to build a target that does not match the running host."""
    plat, machines = TARGETS[target]
    machine = platform.machine().lower()
    if not sys.platform.startswith(plat) or machine not in machines:
        raise SystemExit(
            f"target {target} cannot be built on {sys.platform}/{machine}; use a native runner"
        )
    if target == "macos-universal":
        host = sysconfig.get_platform()
        print(f"Python {platform.python_version()} platform: {host}", flush=True)
        if not host.endswith("-universal2"):
            raise SystemExit(
                f"{target} needs a universal2 Python (python.org installer); this one is {host}"
            )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


MACHO_CPUS = {0x01000007: "x86_64", 0x0100000C: "arm64"}
UNIVERSAL_ARCHS = {"x86_64", "arm64"}


def macho_archs(head: bytes) -> set[str] | None:
    """Architectures of a Mach-O file from its first bytes (>= 8 + 32 * slices), else None."""
    if len(head) < 8:
        return None
    magic = int.from_bytes(head[:4], "big")
    if magic in (0xCAFEBABE, 0xCAFEBABF):  # fat binary (fat_arch / fat_arch_64 table)
        count = int.from_bytes(head[4:8], "big")
        if not 0 < count <= 8:  # Java class files share the magic
            return None
        stride = 20 if magic == 0xCAFEBABE else 32
        cpus = [head[8 + i * stride : 12 + i * stride] for i in range(count)]
        return {MACHO_CPUS.get(int.from_bytes(cpu, "big"), "other") for cpu in cpus}
    if head[:4] in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe"):  # thin, little-endian
        return {MACHO_CPUS.get(int.from_bytes(head[4:8], "little"), "other")}
    return None


def macho_file_archs(path: Path) -> set[str] | None:
    with open(path, "rb") as fh:
        return macho_archs(fh.read(8 + 32 * 8))


def download(
    url: str, dest: Path, sha256: str | None = None, attempts: int = 3
) -> Path:
    """Download url to dest (reusing a cached copy), verifying sha256 when given."""
    if dest.exists() and (sha256 is None or sha256_file(dest) == sha256):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    for attempt in range(1, attempts + 1):
        try:
            print(f"downloading {url}", flush=True)
            request = urllib.request.Request(
                url, headers={"User-Agent": "TunnelFlare-build"}
            )
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                open(part, "wb") as fh,
            ):
                shutil.copyfileobj(response, fh, 1 << 20)
            break
        except OSError as exc:
            if attempt == attempts:
                raise SystemExit(f"download failed: {url}: {exc}") from exc
            print(f"  attempt {attempt} failed ({exc}); retrying", flush=True)
            time.sleep(3 * attempt)
    if sha256 is not None:
        actual = sha256_file(part)
        if actual != sha256:
            part.unlink()
            raise SystemExit(
                f"sha256 mismatch for {url}\n  expected {sha256}\n  actual   {actual}"
            )
    os.replace(part, dest)
    return dest


def run(cmd: list, **kwargs) -> subprocess.CompletedProcess:
    print("+ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def rel(path: Path) -> str:
    """Path relative to the repo root, POSIX style (used in build-info.json)."""
    return Path(path).resolve().relative_to(ROOT).as_posix()
