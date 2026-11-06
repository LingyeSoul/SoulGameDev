"""Palette data for the demo project.

Rules for this file:
- Colours live here, never in a drawing function.
- Roles are named by job (ink, cloak, flame), not by hue.
- A biome reuses the base palette with one explicit HSV transform.
"""

from __future__ import annotations

from tools.art._lib.pixel_lib import Color, hexc, shift

PALETTE: dict[str, Color] = {
    "ink": hexc("#07090f", 255),
    "cloak_dark": hexc("#1b2731", 255),
    "cloak": hexc("#2d4150", 255),
    "cloak_light": hexc("#4a6a80", 255),
    "trim_dark": hexc("#6d4a22", 255),
    "trim": hexc("#b9853c", 255),
    "trim_light": hexc("#e6bd74", 255),
    "flame_deep": hexc("#e8792a", 255),
    "flame": hexc("#ffc45e", 255),
    "flame_core": hexc("#fff6d8", 255),
    "eye": hexc("#d6ece4", 255),
    "panel_dark": hexc("#12161f", 255),
    "panel": hexc("#1b2230", 255),
    "panel_light": hexc("#2b3647", 255),
    "border": hexc("#4c5f77", 255),
}

# One biome transform keeps a family coherent while changing the mood.
BIOMES: dict[str, tuple[float, float, float]] = {
    "default": (0.0, 0.0, 0.0),
    "cold": (-0.04, 0.06, -0.02),
    "ash": (0.03, -0.04, -0.03),
}


def biome_palette(name: str) -> dict[str, Color]:
    if name not in BIOMES:
        raise KeyError(f"unknown biome {name!r}; add it to BIOMES")
    dh, ds, dv = BIOMES[name]
    return {role: shift(color, dh, ds, dv) for role, color in PALETTE.items()}
