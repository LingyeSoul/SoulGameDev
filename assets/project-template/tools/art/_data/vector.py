"""Colour roles for smooth vector assets.

Vector assets share the project's semantic palette but not its pixel-art ramps
or 1 px ink outline. Keep every hex value here; drawing modules pass role names
only.
"""

from __future__ import annotations

from tools.art._data.palette import PALETTE
from tools.art._lib.svg_lib import HexColor, rgba_to_hex

VECTOR_PALETTE: dict[str, HexColor] = {
    "ink": rgba_to_hex(PALETTE["ink"]),
    "shadow": rgba_to_hex(PALETTE["cloak_dark"]),
    "paper": rgba_to_hex(PALETTE["flame_core"]),
    "accent": rgba_to_hex(PALETTE["trim"]),
    "accent_light": rgba_to_hex(PALETTE["trim_light"]),
}
