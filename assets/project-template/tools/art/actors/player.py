"""Generate exactly one image: art/actors/player.png (a four-frame sheet).

Run directly:
    python tools/art/actors/player.py
Or through the build orchestrator:
    python tools/art/build.py --only actors/player
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.art._data.animations import ANIMATIONS
from tools.art._data.palette import PALETTE
from tools.art._lib.pixel_lib import Canvas, sheet
from tools.art._lib.verify import verify_sprite

CELL_W = 16
CELL_H = 24
FRAME_COUNT = 4


def _draw(step: int, walking: bool) -> Canvas:
    palette = PALETTE
    canvas = Canvas(CELL_W, CELL_H)

    # Cloak: narrow shoulders, wide hem, then a two-row hem band.
    canvas.polygon(
        [(3.0, 7.0), (12.0, 7.0), (13.0, 13.0), (14.0, 19.0), (2.0, 19.0), (2.0, 13.0)],
        palette["cloak"],
    )
    canvas.rect(2, 19, 12, 2, palette["cloak_dark"])
    canvas.rect(2, 7, 11, 2, palette["cloak_light"])

    # Hood and the unlit face opening. The eyes are the only bright detail.
    canvas.ellipse(8.0, 5.0, 3.8, 3.6, palette["cloak"])
    canvas.ellipse(8.0, 5.2, 2.0, 1.9, palette["ink"])
    canvas.set(7, 5, palette["eye"])
    canvas.set(8, 5, palette["eye"])

    # Belt/trim stays one pixel so it survives at native scale.
    canvas.rect(2, 19, 12, 1, palette["trim"])

    # The lantern is the only warm object. It never moves between frames.
    canvas.line(13, 8, 13, 10, palette["trim"])
    canvas.rect(12, 10, 3, 1, palette["trim_dark"])
    canvas.vline(12, 11, 4, palette["trim"])
    canvas.vline(14, 11, 4, palette["trim"])
    canvas.rect(13, 11, 1, 4, palette["flame_deep"])
    canvas.set(13, 12, palette["flame"])
    canvas.set(13, 13, palette["flame_core"])
    canvas.rect(12, 15, 3, 1, palette["trim_dark"])

    # Feet: idle keeps both planted; walk alternates which foot is forward.
    if walking:
        left_y = 22 if step == 0 else 21
        right_y = 21 if step == 0 else 22
    else:
        left_y = 22 if step == 0 else 21
        right_y = 22
    canvas.rect(4, left_y, 3, CELL_H - left_y, palette["cloak_dark"])
    canvas.rect(9, right_y, 3, CELL_H - right_y, palette["cloak_dark"])

    canvas.bevel(
        {
            palette["cloak"]: (palette["cloak_dark"], palette["cloak_light"]),
            palette["cloak_dark"]: (palette["ink"], palette["cloak"]),
            palette["cloak_light"]: (palette["cloak"], palette["trim_light"]),
            palette["trim"]: (palette["trim_dark"], palette["trim_light"]),
        },
        {palette["ink"], palette["flame"], palette["flame_core"], palette["flame_deep"], palette["eye"]},
    )
    canvas.outline(palette["ink"])
    return canvas


def build(root: Path) -> dict:
    frames = [
        _draw(0, False),
        _draw(1, False),
        _draw(0, True),
        _draw(1, True),
    ]
    output = root / "art" / "actors" / "player.png"
    sheet([frames], CELL_W, CELL_H).save(output, 1)

    verify_sprite(
        path=output,
        width=CELL_W * FRAME_COUNT,
        height=CELL_H,
        allowed=set(PALETTE.values()),
        ink=PALETTE["ink"],
        require_alpha=True,
        bottom_row=True,
        max_colors=12,
        outline=True,
    )
    return {
        "kind": "sheet",
        "key": "player",
        "output": "actors/player.png",
        "cell": [CELL_W, CELL_H],
        "pivot": [CELL_W // 2, CELL_H - 1],
        "animations": ANIMATIONS["player"],
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    metadata = build(root)
    print(f"wrote {root / 'art' / metadata['output']}")
