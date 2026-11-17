"""生成安装包图标 —— 必须与界面里的品牌符号一致。

界面用的是 .brand-logo: 圆角方块 + 140deg 渐变 (#3d8fff -> #4956d9) + 白色六边形。
图标按同一套配色和形状生成, 免得装完桌面图标和界面里不是一个东西。

不依赖 Pillow: 构建机 (包括 CI) 不保证有图形库, 所以这里只用标准库
写 PNG, 再拼成多尺寸 ICO。

用法: python windows/make-icon.py <输出 .ico>
"""
from __future__ import annotations

import math
import struct
import sys
import zlib

# 与 app/static/app.css 的 .brand-logo 一致
GRADIENT_FROM = (0x3D, 0x8F, 0xFF)
GRADIENT_TO = (0x49, 0x56, 0xD9)
SIZES = (16, 24, 32, 48, 64, 128, 256)
RADIUS_RATIO = 12 / 39   # 界面上 39px 盒子配 12px 圆角


def _rounded_mask(size: int) -> list[list[bool]]:
    """圆角矩形的像素覆盖判定 (按半径做距离近似, 边缘带抗锯齿)。"""
    radius = max(1.0, size * RADIUS_RATIO)
    mask = [[False] * size for _ in range(size)]
    for y in range(size):
        for x in range(size):
            # 到最近角心的距离
            cx = min(max(x, radius), size - 1 - radius)
            cy = min(max(y, radius), size - 1 - radius)
            dist = math.hypot(x - cx, y - cy)
            mask[y][x] = dist <= radius
    return mask


def _inside_hexagon(x: float, y: float, cx: float, cy: float, r: float) -> bool:
    """尖角朝上的正六边形 (界面里 ⬢ 的形状)。"""
    dx = abs(x - cx)
    dy = abs(y - cy)
    # 六边形可以拆成中间矩形 + 上下两个三角
    half_width = r * math.sqrt(3) / 2
    if dy > r:
        return False
    if dy <= r / 2:
        return dx <= half_width
    slope = half_width / (r / 2)
    return dx <= (r - dy) * slope


def _png(size: int) -> bytes:
    """按 140deg 渐变 + 圆角 + 白色六边形渲染一帧 PNG。"""
    mask = _rounded_mask(size)
    cx = cy = size / 2.0
    hex_r = size * 0.26

    rows = bytearray()
    for y in range(size):
        rows.append(0)   # PNG filter type 0
        for x in range(size):
            t = (x / max(size - 1, 1) * 0.7 + y / max(size - 1, 1) * 0.3)
            base = tuple(
                int(GRADIENT_FROM[i] + (GRADIENT_TO[i] - GRADIENT_FROM[i]) * t)
                for i in range(3)
            )
            if _inside_hexagon(x + 0.5, y + 0.5, cx, cy, hex_r):
                r, g, b = 255, 255, 255
            else:
                r, g, b = base
            alpha = 255 if mask[y][x] else 0
            rows.extend((r, g, b, alpha))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)   # 8bit RGBA
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
            + chunk(b"IEND", b""))


def _ico(frames: list[bytes]) -> bytes:
    """把 PNG 帧拼成 ICO (Windows 10+ 支持 PNG 压缩的 ICO 条目)。"""
    count = len(frames)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = bytearray()
    payloads = bytearray()
    for size, png in zip(SIZES, frames):
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0, 0, 1, 32, len(png), offset,
        )
        payloads += png
        offset += len(png)
    return header + bytes(entries) + bytes(payloads)


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "icon.ico"
    frames = [_png(s) for s in SIZES]
    with open(out, "wb") as fh:
        fh.write(_ico(frames))
    print(f"icon written: {out} ({len(SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
