"""Install universal2 (arm64 + x86_64) builds of dependencies that publish only thin macOS wheels.

Usage: python packaging/universal2.py   (build.py runs it for macos-universal)

For each distribution in THIN_WHEELS whose installed Mach-O files lack an
architecture: download its arm64 and x86_64 wheels with pip --require-hashes
(version and hashes from requirements-dev.txt), merge every Mach-O file with
`lipo -create`, retag the wheel as universal2, rewrite RECORD and install it
into the running environment. PySide6 and shiboken6 already ship universal2
wheels; cloudflared is merged by fetch_cloudflared.py.
"""

from __future__ import annotations

import base64
import hashlib
import re
import subprocess
import sys
import tempfile
import zipfile
from importlib import metadata
from pathlib import Path

import buildlib
from buildlib import BUILD, CACHE, ROOT, run

THIN_WHEELS = ("psutil",)
# Wheels built for at most the app's minimum macOS (LSMinimumSystemVersion in tunnelflare.spec).
MACOS_MIN = "14_0"
WHEEL_ARCHS = ("arm64", "x86_64")


def is_universal(name: str) -> bool:
    files = [
        f.locate()
        for f in metadata.distribution(name).files or []
        if f.suffix in (".so", ".dylib")
    ]
    if not files:
        raise SystemExit(f"{name} has no installed extension modules")
    return all(
        buildlib.UNIVERSAL_ARCHS <= (buildlib.macho_file_archs(Path(f)) or set())
        for f in files
    )


def locked_requirement(name: str) -> str:
    """'name==version --hash=...' for name from requirements-dev.txt."""
    text = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    for line in text.replace("\\\n", " ").splitlines():
        if re.match(rf"{re.escape(name)}==", line.strip(), re.IGNORECASE):
            return " ".join(line.split())
    raise SystemExit(f"{name} is not pinned in requirements-dev.txt")


def download_wheel(requirement: str, arch: str) -> Path:
    name, version = requirement.split()[0].split("==")
    dest = CACHE / "wheels" / arch
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        req_file = Path(tmp) / "requirements.txt"
        req_file.write_text(requirement + "\n", encoding="utf-8")
        py = f"{sys.version_info.major}{sys.version_info.minor}"
        run(
            [
                sys.executable, "-m", "pip", "download",
                "--require-hashes", "--no-deps", "--only-binary=:all:",
                "--platform", f"macosx_{MACOS_MIN}_{arch}",
                "--python-version", py, "--implementation", "cp",
                "--abi", f"cp{py}", "--abi", "abi3",
                "--dest", dest, "-r", req_file,
            ]
        )  # fmt: skip
    wheels = sorted(dest.glob(f"{name.replace('-', '_')}-{version}-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected one {name} {version} wheel for {arch} in {dest}, found {wheels}")
    return wheels[0]


def record_hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return "sha256=" + digest.decode()


def lipo(slices: list[bytes]) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for index, data in enumerate(slices):
            paths.append(Path(tmp) / f"slice{index}")
            paths[-1].write_bytes(data)
        out = Path(tmp) / "universal"
        subprocess.run(["lipo", "-create", "-output", out, *paths], check=True)
        return out.read_bytes()


def fuse_wheels(arm64: Path, x86_64: Path, out_dir: Path) -> Path:
    """Merge a thin arm64 and a thin x86_64 wheel into one universal2 wheel."""
    stem_parts = arm64.name[: -len(".whl")].split("-")
    if len(stem_parts) != 5:
        raise SystemExit(f"unsupported wheel name {arm64.name}")
    name, version, py_tag, abi_tag, _ = stem_parts
    versions = [
        tuple(int(n) for n in re.search(r"macosx_(\d+)_(\d+)_", wheel.name).groups())
        for wheel in (arm64, x86_64)
    ]
    major, minor = max(versions)
    platform_tag = f"macosx_{major}_{minor}_universal2"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}-{version}-{py_tag}-{abi_tag}-{platform_tag}.whl"

    with zipfile.ZipFile(arm64) as zarm, zipfile.ZipFile(x86_64) as zx86:
        if sorted(zarm.namelist()) != sorted(zx86.namelist()):
            raise SystemExit(f"{arm64.name} and {x86_64.name} contain different files")
        record_name = next(
            n for n in zarm.namelist() if n.endswith(".dist-info/RECORD")
        )
        records = []
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zarm.infolist():
                if info.filename == record_name or info.is_dir():
                    continue
                data = zarm.read(info)
                if buildlib.macho_archs(data[:264]) is not None:
                    data = lipo([data, zx86.read(info.filename)])
                    print(f"  lipo {info.filename}", flush=True)
                elif info.filename.endswith(".dist-info/WHEEL"):
                    lines = [
                        "Tag: " + "-".join(line[5:].split("-")[:2] + [platform_tag])
                        if line.startswith("Tag: ")
                        else line
                        for line in data.decode("utf-8").splitlines()
                    ]
                    data = ("\n".join(lines) + "\n").encode("utf-8")
                entry = zipfile.ZipInfo(info.filename, info.date_time)
                entry.external_attr = info.external_attr
                entry.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(entry, data)
                records.append(f"{info.filename},{record_hash(data)},{len(data)}")
            records.append(f"{record_name},,")
            zout.writestr(record_name, "\n".join(records) + "\n")
    return out


def ensure_universal_wheels() -> None:
    for name in THIN_WHEELS:
        if is_universal(name):
            print(f"{name}: installed build is already universal2", flush=True)
            continue
        requirement = locked_requirement(name)
        thin = [download_wheel(requirement, arch) for arch in WHEEL_ARCHS]
        wheel = fuse_wheels(*thin, BUILD / "wheels")
        run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--no-index",
             "--force-reinstall", wheel]
        )  # fmt: skip
        if not is_universal(name):
            raise SystemExit(f"{name} is still not universal2 after installing {wheel.name}")
        print(f"{name}: installed {wheel.name}", flush=True)


if __name__ == "__main__":
    ensure_universal_wheels()
