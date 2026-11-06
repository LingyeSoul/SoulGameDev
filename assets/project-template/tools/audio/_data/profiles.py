"""Numeric recipes only. Synthesis code lives in each asset module."""

from __future__ import annotations

HIT = {
    "duration": 0.20,
    "thud_hz": 90.0,
    "thud_cutoff": 500.0,
    "thud_decay": 0.055,
    "crack_low": 600.0,
    "crack_high": 5200.0,
    "crack_decay": 0.028,
    "peak": 0.70,
}

ROOM = {
    "length": 8.0,
    "fade": 1.0,
    "bed_gain": 0.55,
    "air_gain": 0.16,
    "drone_hz": 55.0,
    "drone_gain": 0.24,
    "swell_cycles": 2.0,
    "drip_count": 5,
    "drip_gain": 0.10,
    "peak": 0.50,
}
