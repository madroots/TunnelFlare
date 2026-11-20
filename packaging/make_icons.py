"""Render the app icon from tunnelflare_gui/resources/tray.svg.

Usage: python packaging/make_icons.py [--out build/icons]

Writes png/tunnelflare-<size>.png (16..1024), tunnelflare.png (256 px, Linux),
tunnelflare.ico (PNG-compressed entries) and tunnelflare.icns (ic07..ic14).
Rendering uses QSvgRenderer under an offscreen QGuiApplication; the ICO/ICNS
containers are written with struct.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

import buildlib

SVG = buildlib.ROOT / "tunnelflare_gui" / "resources" / "tray.svg"
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# ICNS element type -> pixel size (ic11..ic14 are the @2x variants)
ICNS_TYPES = (
    (b"ic07", 128),
    (b"ic08", 256),
    (b"ic09", 512),
    (b"ic10", 1024),
    (b"ic11", 32),
    (b"ic12", 64),
    (b"ic13", 256),
    (b"ic14", 512),
)


def render_pngs(svg: Path, sizes) -> dict[int, bytes]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])  # noqa: F841 (keep alive)
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        raise SystemExit(f"cannot render {svg}")
    out = {}
    for size in sizes:
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise SystemExit(f"PNG encoding failed at {size}px")
        buffer.close()
        out[size] = bytes(data)
    return out


def build_ico(pngs: dict[int, bytes]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(ICO_SIZES))
    offset = len(header) + 16 * len(ICO_SIZES)
    entries, blobs = b"", b""
    for size in ICO_SIZES:
        data = pngs[size]
        dim = 0 if size >= 256 else size  # 0 means 256 in ICONDIRENTRY
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    return header + entries + blobs


def build_icns(pngs: dict[int, bytes]) -> bytes:
    body = b"".join(
        kind + struct.pack(">I", 8 + len(pngs[size])) + pngs[size]
        for kind, size in ICNS_TYPES
    )
    return b"icns" + struct.pack(">I", 8 + len(body)) + body


def make_icons(out: Path) -> None:
    pngs = render_pngs(SVG, PNG_SIZES)
    (out / "png").mkdir(parents=True, exist_ok=True)
    for size, data in pngs.items():
        (out / "png" / f"tunnelflare-{size}.png").write_bytes(data)
    (out / "tunnelflare.png").write_bytes(pngs[256])
    (out / "tunnelflare.ico").write_bytes(build_ico(pngs))
    (out / "tunnelflare.icns").write_bytes(build_icns(pngs))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=buildlib.ICONS)
    args = parser.parse_args()
    make_icons(args.out.resolve())
    print(args.out.resolve())


if __name__ == "__main__":
    main()
