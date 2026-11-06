"""Animation tables. Timing is data, not drawing code.

Frame coordinates are [row, column] inside the generated sheet.
"""

from __future__ import annotations

ANIMATIONS: dict[str, dict[str, dict]] = {
    "player": {
        "idle": {
            "frames": [[0, 0], [0, 1]],
            "fps": 6,
            "loop": True,
        },
        "walk": {
            "frames": [[0, 2], [0, 3]],
            "fps": 8,
            "loop": True,
        },
    },
}
