"""Generate exactly one file: art/audio/sfx_hit.wav."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
from synthesizer import Waveform

from tools.audio._data.profiles import HIT
from tools.audio._lib.audio_lib import (
    SAMPLE_RATE,
    bandpass,
    exp_env,
    mix,
    noise,
    normalize,
    samples,
    tone,
    verify_audio,
    write_wav,
)

SEED = 20261104


def build(root: Path) -> dict:
    rng = np.random.default_rng(SEED)
    length = samples(HIT["duration"], SAMPLE_RATE)

    thud = tone(
        Waveform.sine,
        HIT["thud_hz"],
        HIT["duration"],
        HIT["thud_cutoff"],
        0.9,
        0.0,
        0.0,
        SAMPLE_RATE,
        SEED,
    ) * exp_env(length, 0.002, HIT["thud_decay"], SAMPLE_RATE)

    crack = bandpass(
        noise(HIT["duration"], "white", SAMPLE_RATE, rng),
        HIT["crack_low"],
        HIT["crack_high"],
        2,
        SAMPLE_RATE,
    ) * exp_env(length, 0.001, HIT["crack_decay"], SAMPLE_RATE)

    signal = normalize(mix([(thud, 1.0), (crack, 0.55)]), HIT["peak"])
    output = root / "art" / "audio" / "sfx_hit.wav"
    write_wav(output, signal, SAMPLE_RATE, "PCM_16")

    verify_audio(
        path=output,
        rate=SAMPLE_RATE,
        channels=1,
        subtype="PCM_16",
        peak_min=0.60,
        peak_max=0.80,
        duration_min=0.18,
        duration_max=0.22,
        seam_max=None,
    )
    return {
        "kind": "audio",
        "key": "hit",
        "output": "audio/sfx_hit.wav",
        "bus": "SFX",
        "loop": False,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    metadata = build(root)
    print(f"wrote {root / 'art' / metadata['output']}")
