"""Shared pixel primitives for deterministic, palette-driven sprites.

This module contains no game content: no palettes, no asset names, no timings.
Asset modules import it, pass explicit colours, and own exactly one output image.
Every primitive writes whole pixels; there is no anti-aliasing and no gradient.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image

Color = tuple[int, int, int, int]
TRANSPARENT: Color = (0, 0, 0, 0)


def hexc(value: str, alpha: int) -> Color:
    """Turn ``#rrggbb`` into an explicit RGBA tuple."""
    raw = value.lstrip("#")
    if len(raw) != 6:
        raise ValueError(f"expected #rrggbb, got {value!r}")
    if not 0 <= alpha <= 255:
        raise ValueError(f"alpha must be 0..255, got {alpha}")
    return (
        int(raw[0:2], 16),
        int(raw[2:4], 16),
        int(raw[4:6], 16),
        alpha,
    )


def with_alpha(color: Color, alpha: int) -> Color:
    if not 0 <= alpha <= 255:
        raise ValueError(f"alpha must be 0..255, got {alpha}")
    return (color[0], color[1], color[2], alpha)


def shift(color: Color, dh: float, ds: float, dv: float) -> Color:
    """Rotate hue and offset saturation/value in HSV space."""
    import colorsys

    r, g, b, a = color
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    h = (h + dh) % 1.0
    s = max(0.0, min(1.0, s + ds))
    v = max(0.0, min(1.0, v + dv))
    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
    return (round(nr * 255), round(ng * 255), round(nb * 255), a)


def mix(a: Color, b: Color, t: float) -> Color:
    if not 0.0 <= t <= 1.0:
        raise ValueError(f"mix factor must be 0..1, got {t}")
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
        round(a[3] + (b[3] - a[3]) * t),
    )


def noise(x: int, y: int, seed: int) -> float:
    """Deterministic value noise in [0, 1) without importing random."""
    n = (x * 374761393 + y * 668265263 + seed * 2246822519) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 65535.0


class Canvas:
    """A mutable pixel buffer. Coordinates are integer pixels, origin top-left."""

    def __init__(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            raise ValueError(f"canvas size must be positive, got {width}x{height}")
        self.w = width
        self.h = height
        self.px: list[list[Color | None]] = [[None] * height for _ in range(width)]

    def set(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[x][y] = color

    def get(self, x: int, y: int) -> Color | None:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[x][y]
        return None

    def opaque(self, x: int, y: int) -> bool:
        color = self.get(x, y)
        return color is not None and color[3] > 0

    def fill(self, color: Color) -> None:
        for y in range(self.h):
            for x in range(self.w):
                self.set(x, y, color)

    def rect(self, x: int, y: int, w: int, h: int, color: Color) -> None:
        for iy in range(y, y + h):
            for ix in range(x, x + w):
                self.set(ix, iy, color)

    def frame(self, x: int, y: int, w: int, h: int, color: Color) -> None:
        self.rect(x, y, w, 1, color)
        self.rect(x, y + h - 1, w, 1, color)
        self.rect(x, y, 1, h, color)
        self.rect(x + w - 1, y, 1, h, color)

    def hline(self, x: int, y: int, w: int, color: Color) -> None:
        self.rect(x, y, w, 1, color)

    def vline(self, x: int, y: int, h: int, color: Color) -> None:
        self.rect(x, y, 1, h, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, color: Color) -> None:
        if rx <= 0 or ry <= 0:
            raise ValueError(f"ellipse radii must be positive, got {rx}x{ry}")
        for y in range(math.floor(cy - ry), math.ceil(cy + ry) + 1):
            for x in range(math.floor(cx - rx), math.ceil(cx + rx) + 1):
                nx = (x - cx) / rx
                ny = (y - cy) / ry
                if nx * nx + ny * ny <= 1.0:
                    self.set(x, y, color)

    def polygon(self, points: Sequence[tuple[float, float]], color: Color) -> None:
        if len(points) < 3:
            raise ValueError(f"polygon needs at least 3 points, got {len(points)}")
        ys = [point[1] for point in points]
        y_min = max(0, math.floor(min(ys)))
        y_max = min(self.h - 1, math.ceil(max(ys)))
        for y in range(y_min, y_max + 1):
            crossings: list[float] = []
            for index in range(len(points)):
                x0, y0 = points[index]
                x1, y1 = points[(index + 1) % len(points)]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    crossings.append(x0 + (x1 - x0) * t)
            crossings.sort()
            for index in range(0, len(crossings) - 1, 2):
                start = math.ceil(crossings[index])
                end = math.floor(crossings[index + 1])
                for x in range(start, end + 1):
                    self.set(x, y, color)

    def blit(self, other: "Canvas", ox: int, oy: int) -> None:
        for y in range(other.h):
            for x in range(other.w):
                color = other.get(x, y)
                if color is not None and color[3] > 0:
                    self.set(ox + x, oy + y, color)

    def shifted(self, dx: int, dy: int) -> "Canvas":
        out = Canvas(self.w, self.h)
        out.blit(self, dx, dy)
        return out

    def scaled(self, x_scale: float, y_scale: float, anchor_x: float, anchor_y: float) -> "Canvas":
        """Nearest-neighbour scale that keeps the anchor pixel fixed."""
        if x_scale <= 0.0 or y_scale <= 0.0:
            raise ValueError(f"scale factors must be positive, got {x_scale}x{y_scale}")
        out = Canvas(self.w, self.h)
        for y in range(self.h):
            src_y = anchor_y + (y - anchor_y) / y_scale
            sy = int(math.floor(src_y + 0.5))
            if sy < 0 or sy >= self.h:
                continue
            for x in range(self.w):
                src_x = anchor_x + (x - anchor_x) / x_scale
                sx = int(math.floor(src_x + 0.5))
                if sx < 0 or sx >= self.w:
                    continue
                color = self.get(sx, sy)
                if color is not None:
                    out.set(x, y, color)
        return out

    def leaned(self, amount: float, anchor_y: int) -> "Canvas":
        """Horizontal shear, strongest at the top, zero at the anchor row."""
        if anchor_y <= 0:
            raise ValueError(f"anchor_y must be positive, got {anchor_y}")
        out = Canvas(self.w, self.h)
        for y in range(self.h):
            weight = (anchor_y - y) / float(anchor_y)
            offset = int(round(amount * weight))
            for x in range(self.w):
                color = self.get(x, y)
                if color is not None:
                    out.set(x + offset, y, color)
        return out

    def mirrored(self) -> "Canvas":
        out = Canvas(self.w, self.h)
        for y in range(self.h):
            for x in range(self.w):
                color = self.get(self.w - 1 - x, y)
                if color is not None:
                    out.set(x, y, color)
        return out

    def recolor(self, mapping: dict[Color, Color]) -> "Canvas":
        out = Canvas(self.w, self.h)
        for y in range(self.h):
            for x in range(self.w):
                color = self.get(x, y)
                if color is not None:
                    out.set(x, y, mapping.get(color, color))
        return out

    def outline(self, color: Color) -> None:
        """Add a one-pixel border around every opaque cluster."""
        edges: list[tuple[int, int]] = []
        for y in range(self.h):
            for x in range(self.w):
                if self.opaque(x, y):
                    continue
                if (
                    self.opaque(x + 1, y)
                    or self.opaque(x - 1, y)
                    or self.opaque(x, y + 1)
                    or self.opaque(x, y - 1)
                ):
                    edges.append((x, y))
        for x, y in edges:
            self.set(x, y, color)

    def seal_outline(self, color: Color) -> None:
        """Fill only missing border pixels; never thicken an existing outline."""
        edges: list[tuple[int, int]] = []
        for y in range(self.h):
            for x in range(self.w):
                if self.opaque(x, y):
                    continue
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    neighbour = self.get(nx, ny)
                    if neighbour is None or neighbour[3] == 0:
                        continue
                    if (neighbour[0], neighbour[1], neighbour[2]) != (color[0], color[1], color[2]):
                        edges.append((x, y))
                        break
        for x, y in edges:
            self.set(x, y, color)

    def bevel(self, ramps: dict[Color, tuple[Color, Color]], skip: set[Color]) -> None:
        """Rim light from the upper-left and contact shadow below."""
        source = [[self.px[x][y] for y in range(self.h)] for x in range(self.w)]
        for y in range(self.h):
            for x in range(self.w):
                base = source[x][y]
                if base is None or base in skip:
                    continue
                ramp = ramps.get(base)
                if ramp is None:
                    continue
                shadow, highlight = ramp
                above = source[x][y - 1] if y > 0 else None
                left = source[x - 1][y] if x > 0 else None
                below = source[x][y + 1] if y < self.h - 1 else None
                if (above is None and y > 0) or (left is None and x > 0):
                    self.set(x, y, highlight)
                elif below is None and y < self.h - 1:
                    self.set(x, y, shadow)

    def tint_near(self, origin: tuple[float, float], radius: float, color: Color, strength: float) -> None:
        if radius <= 0.0:
            raise ValueError(f"radius must be positive, got {radius}")
        if not 0.0 <= strength <= 1.0:
            raise ValueError(f"strength must be 0..1, got {strength}")
        ox, oy = origin
        for y in range(self.h):
            for x in range(self.w):
                current = self.get(x, y)
                if current is None or current[3] == 0:
                    continue
                distance = math.hypot(x - ox, y - oy)
                if distance <= radius:
                    self.set(x, y, mix(current, color, strength * (1.0 - distance / radius)))

    def colors(self) -> set[Color]:
        return {
            color
            for column in self.px
            for color in column
            if color is not None and color[3] > 0
        }

    def to_image(self) -> Image.Image:
        image = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        pixels = image.load()
        for y in range(self.h):
            for x in range(self.w):
                color = self.get(x, y)
                if color is not None:
                    pixels[x, y] = color
        return image

    def save(self, path: Path, scale: int) -> None:
        if scale <= 0:
            raise ValueError(f"scale must be positive, got {scale}")
        path.parent.mkdir(parents=True, exist_ok=True)
        image = self.to_image()
        if scale != 1:
            image = image.resize((self.w * scale, self.h * scale), Image.NEAREST)
        image.save(path, format="PNG", optimize=False)


def sheet(cells: Sequence[Sequence[Canvas]], cell_w: int, cell_h: int) -> Canvas:
    if not cells:
        raise ValueError("sheet needs at least one row")
    if cell_w <= 0 or cell_h <= 0:
        raise ValueError(f"cell size must be positive, got {cell_w}x{cell_h}")
    rows = len(cells)
    columns = max(len(row) for row in cells)
    out = Canvas(cell_w * columns, cell_h * rows)
    for row_index, row in enumerate(cells):
        for column_index, cell in enumerate(row):
            if cell.w != cell_w or cell.h != cell_h:
                raise ValueError(
                    f"cell {row_index},{column_index} is {cell.w}x{cell.h}, expected {cell_w}x{cell_h}"
                )
            out.blit(cell, column_index * cell_w, row_index * cell_h)
    return out


def preview(paths: Iterable[Path], out: Path, columns: int, scale: int, background: Color) -> None:
    """Compose a nearest-neighbour contact sheet for human inspection."""
    images = [Image.open(path).convert("RGBA") for path in paths if path.exists()]
    if not images:
        raise ValueError(f"no existing images to preview for {out}")
    if columns <= 0 or scale <= 0:
        raise ValueError(f"columns and scale must be positive, got {columns}, {scale}")
    cell_w = max(image.width for image in images)
    cell_h = max(image.height for image in images)
    rows = math.ceil(len(images) / columns)
    sheet_image = Image.new("RGBA", (cell_w * columns, cell_h * rows), background)
    for index, image in enumerate(images):
        x = (index % columns) * cell_w
        y = (index // columns) * cell_h
        sheet_image.alpha_composite(image, (x, y))
    sheet_image = sheet_image.resize(
        (sheet_image.width * scale, sheet_image.height * scale),
        Image.NEAREST,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet_image.save(out, format="PNG", optimize=False)
