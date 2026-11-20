"""Download the pinned cloudflared binary for a target and verify it.

Usage: python packaging/fetch_cloudflared.py --target macos-arm64 --dest build/cloudflared/macos-arm64

Downloads are cached under build/cache/cloudflared/<version>/. The asset sha256
(GitHub asset digest) is always checked; for the macOS .tgz the extracted binary
is checked too when cloudflared.json pins binary_sha256. Prints the binary path.
"""

from __future__ import annotations

import argparse
import os
import tarfile
from pathlib import Path

import buildlib


def fetch(target: str, dest: Path) -> Path:
    pin = buildlib.cloudflared_pin()
    if target not in pin["targets"]:
        raise SystemExit(f"no cloudflared pin for target {target}")
    entry = pin["targets"][target]
    version, asset = pin["version"], entry["asset"]
    url = pin["url"].format(version=version, asset=asset)
    archive = buildlib.download(
        url, buildlib.CACHE / "cloudflared" / version / asset, entry["sha256"]
    )

    dest.mkdir(parents=True, exist_ok=True)
    binary = dest / (
        "cloudflared.exe" if target.startswith("windows") else "cloudflared"
    )
    if asset.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as tar:
            member = next(
                (
                    m
                    for m in tar.getmembers()
                    if m.isfile() and Path(m.name).name == "cloudflared"
                ),
                None,
            )
            if member is None:
                raise SystemExit(f"{asset} does not contain a cloudflared binary")
            data = tar.extractfile(member).read()
        tmp = binary.with_name(binary.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, binary)
    else:
        tmp = binary.with_name(binary.name + ".part")
        with open(archive, "rb") as src, open(tmp, "wb") as dst:
            dst.writelines(iter(lambda: src.read(1 << 20), b""))
        os.replace(tmp, binary)

    expected = entry.get("binary_sha256")
    if expected:
        actual = buildlib.sha256_file(binary)
        if actual != expected:
            binary.unlink()
            raise SystemExit(
                f"extracted cloudflared sha256 mismatch for {target}\n  expected {expected}\n  actual   {actual}"
            )
    binary.chmod(0o755)
    return binary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--target", required=True, choices=sorted(buildlib.cloudflared_pin()["targets"])
    )
    parser.add_argument("--dest", required=True, type=Path)
    args = parser.parse_args()
    print(fetch(args.target, args.dest.resolve()))


if __name__ == "__main__":
    main()
