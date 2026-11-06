"""Generate exactly one image: art/ui/panel.png (a 9-slice-friendly panel)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.art._data.palette import PALETTE
from tools.art._lib.pixel_lib import Canvas
from tools.art._lib.verify import verify_sprite

SIZE = 32


def build(root: Path) -> dict:
    palette = PALETTE
    canvas = Canvas(SIZE, SIZE)
    canvas.fill(palette["panel_dark"])
    canvas.frame(0, 0, SIZE, SIZE, palette["ink"])
    canvas.frame(1, 1, SIZE - 2, SIZE - 2, palette["border"])
    canvas.rect(2, 2, SIZE - 4, SIZE - 4, palette["panel"])
    canvas.hline(2, 2, SIZE - 4, palette["panel_light"])
    canvas.vline(2, 2, SIZE - 4, palette["panel_light"])
    canvas.hline(2, SIZE - 3, SIZE - 4, palette["panel_dark"])
    canvas.vline(SIZE - 3, 2, SIZE - 4, palette["panel_dark"])

    # Four brass studs make the frame readable at native scale.
    for x, y in ((3, 3), (SIZE - 6, 3), (3, SIZE - 6), (SIZE - 6, SIZE - 6)):
        canvas.rect(x, y, 3, 3, palette["trim_dark"])
        canvas.set(x + 1, y + 1, palette["trim_light"])

    output = root / "art" / "ui" / "panel.png"
    canvas.save(output, 1)
    verify_sprite(
        path=output,
        width=SIZE,
        height=SIZE,
        allowed=set(PALETTE.values()),
        ink=PALETTE["ink"],
        require_alpha=False,
        bottom_row=False,
        max_colors=8,
        outline=False,
    )
    return {
        "kind": "image",
        "key": "panel",
        "output": "ui/panel.png",
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    metadata = build(root)
    print(f"wrote {root / 'art' / metadata['output']}")
