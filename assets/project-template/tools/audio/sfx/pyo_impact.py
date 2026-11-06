"""Generate exactly one clip: art/audio/sfx_pyo_impact.wav.

pyo is a required dependency (Python 3.12+); install it through the project's
``requirements.txt``. The default audio build discovers this module.

    python tools/audio/build.py --root .
    python tools/audio/build.py --root . --only sfx/pyo_impact
    python tools/audio/sfx/pyo_impact.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.audio._data.pyo_profiles import PYO_IMPACT
from tools.audio._lib.audio_lib import verify_audio
from tools.audio._lib.pyo_lib import render_offline


def _graph(pyo: ModuleType) -> object:
    env = pyo.Adsr(
        attack=PYO_IMPACT["attack"],
        decay=PYO_IMPACT["decay"],
        sustain=0.0,
        release=PYO_IMPACT["release"],
        dur=PYO_IMPACT["duration"],
    )
    sweep = pyo.Linseg(
        [(0.0, PYO_IMPACT["start_hz"]), (PYO_IMPACT["sweep_end"], PYO_IMPACT["end_hz"])],
        loop=False,
        initToFirstVal=True,
    )
    osc = pyo.Sine(freq=sweep, mul=env)
    noise = pyo.Noise(mul=env * PYO_IMPACT["noise_gain"])
    filtered = pyo.Biquad(
        noise,
        freq=PYO_IMPACT["noise_cutoff"],
        q=PYO_IMPACT["noise_q"],
    )
    mixed = osc + filtered
    mixed.out()
    env.play()
    return mixed


def build(root: Path) -> dict:
    output = root / "art" / "audio" / "sfx_pyo_impact.wav"
    render_offline(
        path=output,
        duration=PYO_IMPACT["duration"],
        sample_rate=PYO_IMPACT["sample_rate"],
        channels=1,
        seed=PYO_IMPACT["seed"],
        peak=PYO_IMPACT["peak"],
        graph=_graph,
    )

    verify_audio(
        path=output,
        rate=PYO_IMPACT["sample_rate"],
        channels=1,
        subtype="PCM_16",
        peak_min=PYO_IMPACT["peak"] - 0.05,
        peak_max=PYO_IMPACT["peak"] + 0.05,
        duration_min=PYO_IMPACT["duration"] - 0.02,
        duration_max=PYO_IMPACT["duration"] + 0.02,
        seam_max=None,
        edge_max=PYO_IMPACT["edge_max"],
    )
    return {
        "kind": "audio",
        "key": "pyo_impact",
        "output": "audio/sfx_pyo_impact.wav",
        "bus": "SFX",
        "loop": False,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    metadata = build(root)
    print(f"wrote {root / 'art' / metadata['output']}")
