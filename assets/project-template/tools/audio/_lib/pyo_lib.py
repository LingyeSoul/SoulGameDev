"""Offline DSP rendering with pyo.

pyo is a default audio dependency and needs Python 3.12+. A module imports this
helper when it uses pyo; the helper owns the offline server lifecycle: fixed
sample rate, global seed, PCM16 WAV, normalization, then the caller runs the
same verify_audio gates as every other clip.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

import numpy as np
import soundfile as sf

from tools.audio._lib.audio_lib import normalize, write_wav


def require_pyo() -> ModuleType:
    """Import pyo or fail with an actionable Python-version/dependency error."""
    if sys.version_info < (3, 12):
        raise RuntimeError(
            f"pyo requires Python 3.12+, current interpreter is {sys.version_info.major}."
            f"{sys.version_info.minor}; upgrade the project interpreter"
        )
    try:
        import pyo
    except ImportError as exc:
        raise RuntimeError(
            "pyo is not installed. Run `python -m pip install -r requirements.txt`."
        ) from exc
    return pyo


def render_offline(
    path: Path,
    duration: float,
    sample_rate: int,
    channels: int,
    seed: int,
    peak: float,
    graph: Callable[[ModuleType], object],
) -> None:
    """Render one mono clip with a pyo offline server and normalize it.

    ``graph`` receives the imported pyo module, builds the signal graph, calls
    ``out()`` on the final object, starts any envelopes, and returns the final
    object. The return value is held until rendering finishes; pyo objects that
    lose all Python references are removed from the DSP graph, which would
    silently render silence. Rendering is blocking (``offline`` server), so the
    file is complete when ``start()`` returns. The caller must still run
    ``verify_audio`` on the result.
    """
    if duration <= 0.0:
        raise ValueError(f"duration must be positive, got {duration}")
    if sample_rate <= 0:
        raise ValueError(f"sample_rate must be positive, got {sample_rate}")
    if channels != 1:
        raise ValueError(f"the audio contract is mono; got {channels} channels")
    if not 0.0 < peak <= 1.0:
        raise ValueError(f"peak must be inside (0, 1], got {peak}")
    if seed < 0:
        raise ValueError(f"seed must be non-negative, got {seed}")

    pyo = require_pyo()
    path.parent.mkdir(parents=True, exist_ok=True)

    server = pyo.Server(audio="offline", nchnls=channels)
    server.setSamplingRate(sample_rate)
    server.setGlobalSeed(seed)
    server.recordOptions(
        dur=duration,
        filename=str(path),
        fileformat=0,
        sampletype=0,
    )
    server.boot()
    graph_handle: object | None = None
    try:
        graph_handle = graph(pyo)
        if graph_handle is None:
            raise RuntimeError(
                "graph must return the final pyo object so it stays alive during rendering"
            )
        server.start()
    finally:
        server.shutdown()
        if graph_handle is not None:
            del graph_handle

    if not path.exists():
        raise RuntimeError(f"pyo did not write {path}")

    data, measured_rate = sf.read(path, dtype="float64", always_2d=False)
    if data.ndim != 1:
        raise RuntimeError(f"{path}: expected mono samples, got shape {data.shape}")
    if measured_rate != sample_rate:
        raise RuntimeError(f"{path}: pyo wrote {measured_rate} Hz, expected {sample_rate}")
    if data.size == 0:
        raise RuntimeError(f"{path}: pyo rendered no samples")
    if float(np.max(np.abs(data))) < 1e-9:
        raise RuntimeError(f"{path}: pyo rendered silence")

    write_wav(path, normalize(data, peak), sample_rate, "PCM_16")
