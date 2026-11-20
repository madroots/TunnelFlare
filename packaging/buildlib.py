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

# Build targets -> (sys.platform prefix, accepted platform.machine() values)
TARGETS = {
    "linux-x86_64": ("linux", {"x86_64", "amd64"}),
    "macos-arm64": ("darwin", {"arm64"}),
    "macos-x86_64": ("darwin", {"x86_64"}),
    "windows-x64": ("win32", {"amd64", "x86_64"}),
}


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
