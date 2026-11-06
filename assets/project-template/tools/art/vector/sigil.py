"""Generate exactly one vector asset: art/vector/sigil.svg and its PNG raster.

The SVG is the source asset. The PNG is a deterministic CairoSVG raster for
engines that cannot import SVG; both are produced by this module.

Run directly:
    python tools/art/vector/sigil.py
Or through the build orchestrator:
    python tools/art/build.py --only vector/sigil
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.art._data.vector import VECTOR_PALETTE
from tools.art._lib.svg_lib import SvgCanvas, rasterize
from tools.art._lib.verify import verify_raster, verify_vector

SIZE = 64
RASTER_SCALE = 2

OUTER = (
    "M32 3 L59 15 L59 38 C59 50 48 59 32 62 "
    "C16 59 5 50 5 38 L5 15 Z"
)
INNER = (
    "M32 9 L53 19 L53 37 C53 46 45 54 32 57 "
    "C19 54 11 46 11 37 L11 19 Z"
)
FLAME = (
    "M32 17 C38 24 40 30 36 36 C34 40 30 41 27 38 "
    "C23 34 24 29 29 25 C28 30 30 32 32 32 "
    "C30 27 30 21 32 17 Z"
)
FLAME_CORE = "M32 27 C34 31 34 34 32 36 C30 34 30 31 32 27 Z"


def build(root: Path) -> dict:
    palette = VECTOR_PALETTE
    canvas = SvgCanvas(SIZE, SIZE, viewbox=(0.0, 0.0, float(SIZE), float(SIZE)))

    canvas.path(OUTER, fill=palette["shadow"], stroke=palette["ink"], stroke_width=2.0)
    canvas.path(INNER, fill=palette["paper"], stroke=palette["ink"], stroke_width=1.0)
    canvas.path(FLAME, fill=palette["accent"], stroke=palette["ink"], stroke_width=1.0)
    canvas.path(FLAME_CORE, fill=palette["accent_light"])
    canvas.circle(18.0, 23.0, 2.0, fill=palette["accent"])
    canvas.circle(46.0, 23.0, 2.0, fill=palette["accent"])

    svg_output = root / "art" / "vector" / "sigil.svg"
    png_output = root / "art" / "vector" / "sigil.png"
    canvas.save(svg_output)
    rasterize(svg_output, png_output, scale=RASTER_SCALE, background=None)

    verify_vector(
        path=svg_output,
        width=SIZE,
        height=SIZE,
        allowed=set(palette.values()),
    )
    verify_raster(
        path=png_output,
        width=SIZE * RASTER_SCALE,
        height=SIZE * RASTER_SCALE,
        require_alpha=True,
    )
    return {
        "kind": "vector",
        "key": "sigil",
        "output": "vector/sigil.svg",
        "raster": "vector/sigil.png",
        "size": [SIZE, SIZE],
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    metadata = build(root)
    print(f"wrote {root / 'art' / metadata['output']} and {root / 'art' / metadata['raster']}")
