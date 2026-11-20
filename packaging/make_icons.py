"""Render the app icon from tunnelflare_gui/resources/tray.svg.

Usage: python packaging/make_icons.py [--out build/icons]

Writes png/tunnelflare-<size>.png (16..1024, the bare swirl), tunnelflare.png
(256 px, Linux), tunnelflare.ico (PNG-compressed entries) and tunnelflare.icns
(ic07..ic14). The ICNS uses the macOS icon grid instead: the swirl centered on a
dark rounded-square tile, also written as png/tunnelflare-macos-<size>.png.
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

# macOS icon grid (Big Sur and later) on a 1024 px canvas: an 824 px tile with
# ~22% corner radius, centered with room for its drop shadow; the artwork
# spans ~62% of the tile. Tile colors follow the app's card gradient.
MAC_TILE = 824 / 1024
MAC_RADIUS = 0.2237
MAC_ART = 0.62
MAC_TILE_TOP, MAC_TILE_BOTTOM = "#232323", "#1c1c1c"


def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance() or QGuiApplication([sys.argv[0]])


def _renderer(svg: Path):
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        raise SystemExit(f"cannot render {svg}")
    return renderer


def _paint(size: int, draw) -> bytes:
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    draw(painter, size)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise SystemExit(f"PNG encoding failed at {size}px")
    buffer.close()
    return bytes(data)


def render_pngs(svg: Path, sizes) -> dict[int, bytes]:
    from PySide6.QtCore import QRectF

    renderer = _renderer(svg)
    return {
        size: _paint(size, lambda p, s: renderer.render(p, QRectF(0, 0, s, s)))
        for size in sizes
    }


def artwork_bounds(renderer) -> tuple[float, float, float, float]:
    """Bounding box (x, y, w, h) of the SVG's opaque pixels, as fractions of its canvas."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter

    n = 1024
    image = QImage(n, n, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, n, n))
    painter.end()
    alpha = bytes(image.constBits())[3::4]  # ARGB32 is BGRA in memory (little endian)
    rows = [y for y in range(n) if any(alpha[y * n : (y + 1) * n])]
    cols = [x for x in range(n) if any(alpha[x::n])]
    return cols[0] / n, rows[0] / n, (cols[-1] + 1 - cols[0]) / n, (rows[-1] + 1 - rows[0]) / n


def render_macos_pngs(svg: Path, sizes) -> dict[int, bytes]:
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QLinearGradient, QPainterPath, QPen

    renderer = _renderer(svg)
    bx, by, bw, bh = artwork_bounds(renderer)

    def draw(painter, size):
        tile = size * MAC_TILE
        origin = (size - tile) / 2
        rect = QRectF(origin, origin, tile, tile)
        radius = tile * MAC_RADIUS
        painter.setPen(Qt.PenStyle.NoPen)
        # Soft drop shadow below the tile: stacked translucent outsets.
        steps = max(2, round(size * 12 / 1024))
        for i in range(steps, 0, -1):
            spread = size * 10 / 1024 * i / steps
            shadow = QPainterPath()
            shadow.addRoundedRect(
                rect.adjusted(-spread, -spread + size * 6 / 1024, spread, spread + size * 10 / 1024),
                radius + spread,
                radius + spread,
            )
            painter.setBrush(QColor(0, 0, 0, round(60 / steps)))
            painter.drawPath(shadow)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        gradient = QLinearGradient(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
        gradient.setColorAt(0, QColor(MAC_TILE_TOP))
        gradient.setColorAt(1, QColor(MAC_TILE_BOTTOM))
        painter.setBrush(gradient)
        painter.drawPath(path)
        # Hairline edge highlight, as on Apple's dark icons.
        edge = QPen(QColor(255, 255, 255, 22), max(1.0, size / 512))
        painter.setPen(edge)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        inset = edge.widthF() / 2
        painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), radius - inset, radius - inset)
        # Swirl: scale its opaque bounds to MAC_ART of the tile and center them.
        scale = tile * MAC_ART / max(bw, bh)
        cx = cy = size / 2
        target = QRectF(cx - (bx + bw / 2) * scale, cy - (by + bh / 2) * scale, scale, scale)
        renderer.render(painter, target)

    return {size: _paint(size, draw) for size in sizes}


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
    app = qt_app()  # noqa: F841 (keeps Qt alive while rendering)
    pngs = render_pngs(SVG, PNG_SIZES)
    mac_pngs = render_macos_pngs(SVG, sorted({size for _, size in ICNS_TYPES}))
    (out / "png").mkdir(parents=True, exist_ok=True)
    for size, data in pngs.items():
        (out / "png" / f"tunnelflare-{size}.png").write_bytes(data)
    for size, data in mac_pngs.items():
        (out / "png" / f"tunnelflare-macos-{size}.png").write_bytes(data)
    (out / "tunnelflare.png").write_bytes(pngs[256])
    (out / "tunnelflare.ico").write_bytes(build_ico(pngs))
    (out / "tunnelflare.icns").write_bytes(build_icns(mac_pngs))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=buildlib.ICONS)
    args = parser.parse_args()
    make_icons(args.out.resolve())
    print(args.out.resolve())


if __name__ == "__main__":
    main()
