#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成应用图标 app.ico：太赫兹单周期脉冲穿过样品的简笔画图标。

用法（在项目根目录下执行）：
    uv run --with pillow python scripts/make_icon.py                  # 生成 app.ico 与预览图
    uv run --with pillow python scripts/make_icon.py --variant ink    # 换风格
    uv run --with pillow python scripts/make_icon.py --preview-only   # 只看预览，不覆盖 app.ico

说明：
- 图形由圆角底板 + 样品板（竖向薄板）+ 零线 + 单周期脉冲波形（高斯一阶导）构成
- 每个尺寸单独渲染（8 倍超采样后降采样），小尺寸自动省略样品板等细节，保证 16x16 下仍清晰
- ICO 采用混合封装：<=128 为 32 位 BMP 帧（兼容性最好），256 为 PNG 帧
"""

from __future__ import annotations

import argparse
import io
import math
import os
import struct

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Windows 常用图标尺寸
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
PREVIEW_SIZES = (16, 24, 32, 48, 64, 96, 128)

# ---------------- 几何参数（均为相对边长的 0~1 坐标） ----------------
TILE_RADIUS = 0.22          # 底板圆角
WAVE_X0, WAVE_X1 = 0.115, 0.885
WAVE_CY = 0.565             # 零线位置（波形在此上下振荡）
WAVE_AMP = 0.30             # 峰值幅度
WAVE_SPAN = 3.4             # 波形横向半区间（以脉冲时间尺度为单位）
SLAB_X0, SLAB_X1 = 0.455, 0.575     # 样品板（波形零点处穿过它）
SLAB_Y0, SLAB_Y1 = 0.155, 0.885
SLAB_RADIUS = 0.024
DETAIL_MIN_SIZE = 40        # 小于该尺寸时省略样品板与零线

_G_PEAK = math.exp(-0.5)    # 高斯一阶导的峰值，用于归一化

# ---------------- 风格定义 ----------------
VARIANTS: dict[str, dict] = {
    "pulse": {
        "label": "蓝青渐变底板 + 白色波形（默认）",
        "tile": ((37, 99, 235), (14, 165, 233)),
        "border": None,
        "wave": (255, 255, 255, 255),
        "slab_fill": (255, 255, 255, 30),
        "slab_line": (255, 255, 255, 105),
        "axis": (255, 255, 255, 62),
    },
    "ink": {
        "label": "白底 + 墨线（纯简笔画）",
        "tile": ((255, 255, 255), (233, 238, 245)),
        "border": (203, 213, 225, 255),
        "wave": (17, 24, 39, 255),
        "slab_fill": (17, 24, 39, 14),
        "slab_line": (17, 24, 39, 90),
        "axis": (17, 24, 39, 70),
    },
    "line": {
        "label": "透明底 + 蓝青渐变线条",
        "tile": None,
        "border": None,
        "wave": "gradient",
        "slab_fill": None,
        "slab_line": (37, 99, 235, 130),
        "axis": (37, 99, 235, 70),
    },
}

_GRADIENT_STROKE = ((29, 78, 216), (6, 182, 212))


# ---------------- 基础绘制工具 ----------------
def _vertical_gradient(size: int, top, bottom) -> Image.Image:
    """生成竖向渐变图（size x size）。"""
    strip = Image.new("RGBA", (1, size))
    for y in range(size):
        t = y / max(size - 1, 1)
        strip.putpixel(
            (0, y),
            tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,),
        )
    return strip.resize((size, size), Image.Resampling.BILINEAR)


def _layer_from_mask(size, mask: Image.Image, fill) -> Image.Image:
    """按 mask 绘制上色图层；fill 为 RGBA 元组或 PIL 图像（渐变）。"""
    if isinstance(fill, Image.Image):
        src = fill.convert("RGBA")
        if src.size != size:
            src = src.resize(size, Image.Resampling.BILINEAR)
    else:
        src = Image.new("RGBA", size, fill)
    return Image.composite(src, Image.new("RGBA", size, (0, 0, 0, 0)), mask)


def _tile_mask(size, radius: float) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255
    )
    return mask


def _slab_mask(size, scale: int, fill: bool) -> Image.Image:
    mask = Image.new("L", size, 0)
    w, h = size
    box = [
        SLAB_X0 * w,
        SLAB_Y0 * h,
        SLAB_X1 * w,
        SLAB_Y1 * h,
    ]
    radius = SLAB_RADIUS * w
    drawer = ImageDraw.Draw(mask)
    if fill:
        drawer.rounded_rectangle(box, radius=radius, fill=255)
    else:
        width = _stroke_width(scale, 0.017 * (w / scale))
        drawer.rounded_rectangle(box, radius=radius, outline=255, width=width)
    return mask


def _stroke_width(scale: int, final_px: float, minimum: float = 1.0) -> int:
    """把「最终像素宽度」换算为超采样画布上的像素宽度。"""
    return max(1, int(round(max(final_px, minimum) * scale)))


def _polyline_mask(size, points, width: int) -> Image.Image:
    """折线遮罩，端点补圆实现圆头笔画。"""
    mask = Image.new("L", size, 0)
    drawer = ImageDraw.Draw(mask)
    drawer.line(points, fill=255, width=width, joint="curve")
    r = width / 2.0
    for x, y in (points[0], points[-1]):
        drawer.ellipse([x - r, y - r, x + r, y + r], fill=255)
    return mask


def _wave_points(super_width: int, count: int = 720):
    """单周期太赫兹脉冲：高斯一阶导 f(t) = t·exp(-t²/2)/max，先下凹后上冲。"""
    x0, x1 = WAVE_X0 * super_width, WAVE_X1 * super_width
    points = []
    for i in range(count):
        u = i / (count - 1)
        t = -WAVE_SPAN + 2 * WAVE_SPAN * u
        f = t * math.exp(-0.5 * t * t) / _G_PEAK
        points.append((x0 + (x1 - x0) * u, (WAVE_CY - WAVE_AMP * f) * super_width))
    return points


# ---------------- 单个尺寸的渲染 ----------------
def render(size: int, variant: str = "pulse") -> Image.Image:
    """渲染指定边长的图标（RGBA）。"""
    style = VARIANTS[variant]
    scale = 8 if size <= 64 else 4          # 超采样倍数
    super_size = size * scale
    canvas_size = (super_size, super_size)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

    if style["tile"] is not None:
        gradient = _vertical_gradient(super_size, *style["tile"])
        canvas.alpha_composite(_layer_from_mask(canvas_size, _tile_mask(canvas_size, TILE_RADIUS * super_size), gradient))
        if style["border"] is not None:
            border = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            width = _stroke_width(scale, 0.006 * size)
            ImageDraw.Draw(border).rounded_rectangle(
                [width / 2, width / 2, super_size - 1 - width / 2, super_size - 1 - width / 2],
                radius=TILE_RADIUS * super_size,
                outline=style["border"],
                width=width,
            )
            canvas.alpha_composite(border)

    if size >= DETAIL_MIN_SIZE:
        if style["slab_fill"] is not None:
            canvas.alpha_composite(
                _layer_from_mask(canvas_size, _slab_mask(canvas_size, scale, fill=True), style["slab_fill"])
            )
        if style["slab_line"] is not None:
            canvas.alpha_composite(
                _layer_from_mask(canvas_size, _slab_mask(canvas_size, scale, fill=False), style["slab_line"])
            )
        axis_mask = Image.new("L", canvas_size, 0)
        ImageDraw.Draw(axis_mask).line(
            [
                (WAVE_X0 * super_size, WAVE_CY * super_size),
                (WAVE_X1 * super_size, WAVE_CY * super_size),
            ],
            fill=255,
            width=_stroke_width(scale, 0.010 * size),
        )
        canvas.alpha_composite(_layer_from_mask(canvas_size, axis_mask, style["axis"]))

    wave_width = _stroke_width(scale, 0.056 * size, minimum=1.7)
    wave_mask = _polyline_mask(canvas_size, _wave_points(super_size), wave_width)
    wave_fill = style["wave"]
    if wave_fill == "gradient":
        wave_fill = _vertical_gradient(super_size, *_GRADIENT_STROKE)
    canvas.alpha_composite(_layer_from_mask(canvas_size, wave_mask, wave_fill))

    return canvas.resize((size, size), Image.Resampling.LANCZOS)


# ---------------- ICO 封装 ----------------
def _dib_frame(image: Image.Image) -> bytes:
    """32 位 BMP 帧（BITMAPINFOHEADER + BGRA 数据 + 全零 AND 掩码，行序自下而上）。"""
    width, height = image.size
    raw = image.convert("RGBA").tobytes("raw", "BGRA")
    stride = width * 4
    rows = [raw[y * stride : (y + 1) * stride] for y in range(height)]
    xor_bitmap = b"".join(reversed(rows))
    mask_stride = ((width + 31) // 32) * 4
    and_mask = bytes(mask_stride * height)
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    return header + xor_bitmap + and_mask


def _png_frame(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return buffer.getvalue()


def save_ico(path: str, variant: str, sizes=ICON_SIZES) -> int:
    """写出多尺寸 ICO：<=128 用 BMP 帧，256 用 PNG 帧。"""
    frames = []
    for size in sorted(sizes):
        image = render(size, variant)
        payload = _png_frame(image) if size >= 256 else _dib_frame(image)
        frames.append((size, payload, size >= 256))

    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = len(header) + 16 * len(frames)
    entries, blobs = [], []
    for size, payload, is_png in frames:
        entries.append(
            struct.pack(
                "<BBBBHHII",
                size if size < 256 else 0,
                size if size < 256 else 0,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        blobs.append(payload)
        offset += len(payload)

    with open(path, "wb") as handle:
        handle.write(header)
        for entry in entries:
            handle.write(entry)
        for blob in blobs:
            handle.write(blob)
    return offset


# ---------------- 预览图 ----------------
def build_preview(path: str, variants, sizes=PREVIEW_SIZES) -> None:
    """生成对比预览图：每个风格分别在浅色/深色背景条上排布各尺寸。"""
    gap, pad = 28, 26
    strip_height = max(sizes) + 30
    width = pad * 2 + sum(size + gap for size in sizes)
    height = pad * 2 + len(variants) * (strip_height * 2 + 20)
    sheet = Image.new("RGB", (width, height), (255, 255, 255))

    rendered = {(name, size): render(size, name) for name in variants for size in sizes}
    y = pad
    for name in variants:
        for background in ((244, 246, 249), (30, 32, 36)):
            strip = Image.new("RGB", (width - 2 * pad, strip_height), background)
            x = gap
            for size in sizes:
                icon = rendered[(name, size)]
                strip.paste(icon, (x, (strip_height - size) // 2), icon)
                x += size + gap
            sheet.paste(strip, (pad, y))
            y += strip_height + 6
        y += 14
    sheet.save(path)


# ---------------- 入口 ----------------
def main() -> None:
    parser = argparse.ArgumentParser(description="生成 app.ico（太赫兹脉冲简笔画风格）")
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="pulse", help="图标风格")
    parser.add_argument("--out", default=os.path.join(ROOT, "app.ico"), help="ICO 输出路径")
    parser.add_argument("--preview", default=os.path.join(ROOT, "app_icon_preview.png"), help="预览图输出路径")
    parser.add_argument("--preview-only", action="store_true", help="只生成预览图，不覆盖 app.ico")
    args = parser.parse_args()

    build_preview(args.preview, list(VARIANTS))
    print(f"预览图: {args.preview}")

    if args.preview_only:
        for name, style in VARIANTS.items():
            print(f"  {name:<6} {style['label']}")
        return

    total = save_ico(args.out, args.variant)
    print(f"已生成: {args.out}  ({total / 1024:.1f} KB, 风格: {args.variant} - {VARIANTS[args.variant]['label']})")


if __name__ == "__main__":
    main()
