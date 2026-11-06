"""Generate exactly one file: art/audio/ambience_room.wav (a seamless loop)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
from synthesizer import Waveform

from tools.audio._data.profiles import ROOM
from tools.audio._lib.audio_lib import (
    SAMPLE_RATE,
    add_at,
    bandpass,
    exp_env,
    make_loop,
    noise,
    normalize,
    rotate_to_quiet,
    samples,
    tone,
    verify_audio,
    write_wav,
)

SEED = 20261104


def _drip(frequency: float, duration: float, seed: int) -> np.ndarray:
    length = samples(duration, SAMPLE_RATE)
    return tone(
        Waveform.sine,
        frequency,
        duration,
        None,
        0.8,
        0.0,
        0.0,
        SAMPLE_RATE,
        seed,
    ) * exp_env(length, 0.002, 0.12, SAMPLE_RATE)


def build(root: Path) -> dict:
    rng = np.random.default_rng(SEED + 7)
    total = ROOM["length"] + ROOM["fade"]
    count = samples(total, SAMPLE_RATE)
    time = np.arange(count) / SAMPLE_RATE

    bed = noise(total, "brown", SAMPLE_RATE, rng) * ROOM["bed_gain"]
    air = bandpass(
        noise(total, "white", SAMPLE_RATE, rng),
        300.0,
        1100.0,
        2,
        SAMPLE_RATE,
    ) * ROOM["air_gain"]
    swell = (
        0.55
        + 0.22 * np.sin(2.0 * np.pi * time / ROOM["length"] * ROOM["swell_cycles"])
        + 0.12 * np.sin(2.0 * np.pi * time / ROOM["length"] * 5.0)
    )
    signal = (bed + air) * swell

    drone = tone(
        Waveform.sine,
        ROOM["drone_hz"],
        total,
        220.0,
        0.7,
        0.0,
        0.0,
        SAMPLE_RATE,
        SEED,
    ) * ROOM["drone_gain"]
    signal += drone

    for index in range(ROOM["drip_count"]):
        at = rng.uniform(0.4, ROOM["length"] - 0.4)
        frequency = rng.uniform(740.0, 1180.0)
        add_at(signal, at, _drip(frequency, 0.45, SEED + index), ROOM["drip_gain"], SAMPLE_RATE)

    looped = make_loop(signal, ROOM["length"], ROOM["fade"], SAMPLE_RATE)
    looped = rotate_to_quiet(looped, 0.04, SAMPLE_RATE)
    looped = normalize(looped, ROOM["peak"])

    output = root / "art" / "audio" / "ambience_room.wav"
    write_wav(output, looped, SAMPLE_RATE, "PCM_16")

    verify_audio(
        path=output,
        rate=SAMPLE_RATE,
        channels=1,
        subtype="PCM_16",
        peak_min=0.42,
        peak_max=0.60,
        duration_min=7.9,
        duration_max=8.1,
        seam_max=0.04,
    )
    return {
        "kind": "audio",
        "key": "room",
        "output": "audio/ambience_room.wav",
        "bus": "Music",
        "loop": True,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    metadata = build(root)
    print(f"wrote {root / 'art' / metadata['output']}")
