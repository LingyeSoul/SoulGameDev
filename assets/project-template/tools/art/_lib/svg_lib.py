"""Deterministic SVG authoring with svgwrite and rasterization with CairoSVG.

Vector assets are smooth, resolution-independent drawings for UI, icons, logos
and overlays. They are deliberately separate from the pixel-art rules: vector
edges may be anti-aliased, and palette ramps/1 px outlines do not apply.

A module owns one SVG source and may write one derived PNG raster for engines
that cannot import SVG. CairoSVG performs that rasterization; it is never used
to author the shape.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

import svgwrite

HexColor = str


def rgba_to_hex(color: tuple[int, int, int, int]) -> HexColor:
    """Convert an opaque RGBA tuple from the project palette to ``#rrggbb``."""
    red, green, blue, alpha = color
    if alpha != 255:
        raise ValueError(f"vector palette colours must be opaque, got alpha {alpha}")
    for channel in (red, green, blue):
        if not 0 <= channel <= 255:
            raise ValueError(f"colour channel must be 0..255, got {channel}")
    return f"#{red:02x}{green:02x}{blue:02x}"


def check_hex(value: str) -> HexColor:
    """Validate and normalise a ``#rrggbb`` colour used by an SVG module."""
    if not isinstance(value, str):
        raise TypeError(f"expected a #rrggbb string, got {type(value).__name__}")
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value) is None:
        raise ValueError(f"expected #rrggbb, got {value!r}")
    return value.lower()


class SvgCanvas:
    """A small, deterministic wrapper around ``svgwrite.Drawing``.

    Coordinates are SVG user units (normally pixels). The wrapper only exposes
    primitives whose output is fully determined by their arguments; no random
    ids, timestamps or external references are introduced.
    """

    def __init__(
        self,
        width: int,
        height: int,
        viewbox: tuple[float, float, float, float] | None,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError(f"SVG size must be positive, got {width}x{height}")
        self.width = width
        self.height = height
        self._drawing = svgwrite.Drawing(size=(width, height))
        if viewbox is not None:
            self._drawing.viewbox(*viewbox)

    @property
    def drawing(self) -> svgwrite.Drawing:
        """Escape hatch for primitives the wrapper does not cover yet."""
        return self._drawing

    @staticmethod
    def _fill_attributes(
        fill: HexColor,
        stroke: HexColor | None,
        stroke_width: float,
        fill_opacity: float,
    ) -> dict[str, object]:
        if not 0.0 <= fill_opacity <= 1.0:
            raise ValueError(f"fill_opacity must be 0..1, got {fill_opacity}")
        attributes: dict[str, object] = {
            "fill": check_hex(fill),
            "fill_opacity": fill_opacity,
        }
        if stroke is None:
            if stroke_width != 0.0:
                raise ValueError("stroke_width requires a stroke colour")
            return attributes
        if stroke_width <= 0.0:
            raise ValueError(
                f"stroke_width must be positive when a stroke is set, got {stroke_width}"
            )
        attributes["stroke"] = check_hex(stroke)
        attributes["stroke_width"] = stroke_width
        return attributes

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: HexColor,
        stroke: HexColor | None = None,
        stroke_width: float = 0.0,
        radius: float = 0.0,
        fill_opacity: float = 1.0,
    ) -> None:
        self._drawing.add(
            self._drawing.rect(
                insert=(x, y),
                size=(width, height),
                rx=radius,
                ry=radius,
                **self._fill_attributes(fill, stroke, stroke_width, fill_opacity),
            )
        )

    def circle(
        self,
        cx: float,
        cy: float,
        radius: float,
        fill: HexColor,
        stroke: HexColor | None = None,
        stroke_width: float = 0.0,
        fill_opacity: float = 1.0,
    ) -> None:
        self._drawing.add(
            self._drawing.circle(
                center=(cx, cy),
                r=radius,
                **self._fill_attributes(fill, stroke, stroke_width, fill_opacity),
            )
        )

    def ellipse(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        fill: HexColor,
        stroke: HexColor | None = None,
        stroke_width: float = 0.0,
        fill_opacity: float = 1.0,
    ) -> None:
        self._drawing.add(
            self._drawing.ellipse(
                center=(cx, cy),
                r=(rx, ry),
                **self._fill_attributes(fill, stroke, stroke_width, fill_opacity),
            )
        )

    def line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        stroke: HexColor,
        stroke_width: float,
    ) -> None:
        if stroke_width <= 0.0:
            raise ValueError(f"stroke_width must be positive, got {stroke_width}")
        self._drawing.add(
            self._drawing.line(
                start=start,
                end=end,
                stroke=check_hex(stroke),
                stroke_width=stroke_width,
            )
        )

    def polygon(
        self,
        points: Sequence[tuple[float, float]],
        fill: HexColor,
        stroke: HexColor | None = None,
        stroke_width: float = 0.0,
        fill_opacity: float = 1.0,
    ) -> None:
        if len(points) < 3:
            raise ValueError(f"polygon needs at least 3 points, got {len(points)}")
        self._drawing.add(
            self._drawing.polygon(
                points=points,
                **self._fill_attributes(fill, stroke, stroke_width, fill_opacity),
            )
        )

    def path(
        self,
        d: str,
        fill: HexColor,
        stroke: HexColor | None = None,
        stroke_width: float = 0.0,
        fill_opacity: float = 1.0,
    ) -> None:
        if not d.strip():
            raise ValueError("path data must not be empty")
        self._drawing.add(
            self._drawing.path(
                d=d,
                **self._fill_attributes(fill, stroke, stroke_width, fill_opacity),
            )
        )

    def save(self, path: Path) -> None:
        """Write deterministic, human-diffable SVG with a stable element order."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self._drawing.saveas(str(path), pretty=True)


def rasterize(svg_path: Path, png_path: Path, scale: int, background: str | None) -> None:
    """Rasterize an SVG with CairoSVG.

    ``scale`` must be a positive integer; a fractional scale would put vector
    edges on a non-integer pixel grid. A missing Cairo library is reported as
    an actionable error instead of a silent fallback, because a missing PNG
    would otherwise break the manifest.
    """
    if not isinstance(scale, int) or scale <= 0:
        raise ValueError(f"raster scale must be a positive integer, got {scale!r}")
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG source missing: {svg_path}")

    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError(
            "CairoSVG is not installed. Run `python -m pip install -r requirements.txt`."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "CairoSVG could not load the cairo library. Install a Cairo runtime "
            "(for example the GTK 3 runtime on Windows) and re-run the build."
        ) from exc

    png_path.parent.mkdir(parents=True, exist_ok=True)
    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        scale=scale,
        background_color=background,
    )
