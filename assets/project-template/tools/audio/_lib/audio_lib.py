"""Shared audio primitives: synthesizer for tonal layers, numpy/scipy for beds.

This module contains no game content. One asset module owns one output file;
profiles live in tools/audio/_data, envelopes and mixing live here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt
from synthesizer import FilterType, Synthesizer, Waveform

SAMPLE_RATE = 22050


class AudioCheckError(RuntimeError):
    """Raised when a generated audio file violates its declared contract."""


def samples(seconds: float, rate: int) -> int:
    if seconds < 0.0:
        raise ValueError(f"duration must be non-negative, got {seconds}")
    if rate <= 0:
        raise ValueError(f"rate must be positive, got {rate}")
    return int(round(seconds * rate))


def adsr(length: int, attack: float, decay: float, sustain: float, release: float, rate: int) -> np.ndarray:
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")
    if not 0.0 <= sustain <= 1.0:
        raise ValueError(f"sustain must be 0..1, got {sustain}")
    attack_count = min(samples(attack, rate), length)
    decay_count = min(samples(decay, rate), length - attack_count)
    release_count = min(samples(release, rate), length - attack_count - decay_count)
    sustain_count = length - attack_count - decay_count - release_count
    parts: list[np.ndarray] = []
    if attack_count > 0:
        parts.append(np.linspace(0.0, 1.0, attack_count, endpoint=False))
    if decay_count > 0:
        parts.append(np.linspace(1.0, sustain, decay_count, endpoint=False))
    if sustain_count > 0:
        parts.append(np.full(sustain_count, sustain))
    if release_count > 0:
        parts.append(np.linspace(sustain, 0.0, release_count))
    if not parts:
        return np.zeros(length)
    envelope = np.concatenate(parts)
    if envelope.size >= length:
        return envelope[:length]
    return np.pad(envelope, (0, length - envelope.size), mode="edge")


def exp_env(length: int, attack: float, decay: float, rate: int) -> np.ndarray:
    """Percussive envelope: short linear attack, exponential tail."""
    if length <= 0:
        raise ValueError(f"length must be positive, got {length}")
    if decay <= 0.0:
        raise ValueError(f"decay must be positive, got {decay}")
    attack_count = max(1, min(samples(attack, rate), length))
    time = np.arange(length) / rate
    envelope = np.exp(-time / decay)
    envelope[:attack_count] *= np.linspace(0.0, 1.0, attack_count)
    return envelope


def tone(
    waveform: Waveform,
    frequency: float,
    duration: float,
    cutoff: float | None,
    resonance: float,
    detune: float,
    second_volume: float,
    rate: int,
    seed: int,
) -> np.ndarray:
    if frequency <= 0.0:
        raise ValueError(f"frequency must be positive, got {frequency}")
    synth = Synthesizer(
        osc1_waveform=waveform,
        osc1_volume=1.0,
        use_osc2=detune > 0.0,
        osc2_waveform=waveform,
        osc2_volume=second_volume,
        osc2_detune=detune,
        filter_type=FilterType.lowpass if cutoff is not None else None,
        filter_cutoff=cutoff if cutoff is not None else 1000.0,
        filter_resonance=resonance,
        rate=rate,
        seed=seed,
    )
    return np.asarray(synth.generate_constant_wave(frequency, duration), dtype=np.float64)


def noise(duration: float, color: str, rate: int, rng: np.random.Generator) -> np.ndarray:
    count = samples(duration, rate)
    if count <= 0:
        raise ValueError(f"duration produces no samples: {duration}")
    white = rng.normal(0.0, 1.0, count)
    if color == "white":
        signal = white
    elif color == "pink":
        sos = butter(3, [80.0, 2400.0], btype="bandpass", fs=rate, output="sos")
        signal = sosfilt(sos, white)
    elif color == "brown":
        signal = np.cumsum(white)
        signal -= np.linspace(signal[0], signal[-1], count)
    else:
        raise ValueError(f"unknown noise colour {color!r}; use white, pink or brown")
    peak = float(np.max(np.abs(signal)))
    if peak < 1e-9:
        raise RuntimeError("noise generator produced silence")
    return signal / peak


def lowpass(signal: np.ndarray, cutoff: float, order: int, rate: int) -> np.ndarray:
    if cutoff <= 0.0 or cutoff >= rate / 2.0:
        raise ValueError(f"cutoff must be inside (0, {rate / 2.0}), got {cutoff}")
    sos = butter(order, cutoff, btype="lowpass", fs=rate, output="sos")
    return sosfilt(sos, signal)


def highpass(signal: np.ndarray, cutoff: float, order: int, rate: int) -> np.ndarray:
    if cutoff <= 0.0 or cutoff >= rate / 2.0:
        raise ValueError(f"cutoff must be inside (0, {rate / 2.0}), got {cutoff}")
    sos = butter(order, cutoff, btype="highpass", fs=rate, output="sos")
    return sosfilt(sos, signal)


def bandpass(signal: np.ndarray, low: float, high: float, order: int, rate: int) -> np.ndarray:
    if low <= 0.0 or high >= rate / 2.0 or low >= high:
        raise ValueError(f"invalid band {low}..{high} at rate {rate}")
    sos = butter(order, [low, high], btype="bandpass", fs=rate, output="sos")
    return sosfilt(sos, signal)


def add_at(buffer: np.ndarray, at: float, event: np.ndarray, gain: float, rate: int) -> None:
    """Add an event at a time, clipping only at the buffer end."""
    start = samples(at, rate)
    if start >= buffer.size or event.size == 0:
        return
    end = min(buffer.size, start + event.size)
    buffer[start:end] += event[: end - start] * gain


def mix(layers: Sequence[tuple[np.ndarray, float]]) -> np.ndarray:
    if not layers:
        raise ValueError("mix needs at least one layer")
    size = max(layer[0].size for layer in layers)
    output = np.zeros(size)
    for layer, gain in layers:
        output[: layer.size] += layer * gain
    return output


def normalize(signal: np.ndarray, peak: float) -> np.ndarray:
    if not 0.0 < peak <= 1.0:
        raise ValueError(f"peak must be inside (0, 1], got {peak}")
    current = float(np.max(np.abs(signal)))
    if current < 1e-9:
        raise RuntimeError("cannot normalize silence")
    return signal / current * peak


def write_wav(path: Path, signal: np.ndarray, rate: int, subtype: str) -> None:
    if signal.ndim != 1:
        raise ValueError(f"the audio contract is mono; got shape {signal.shape}")
    if float(np.max(np.abs(signal))) > 1.0:
        raise ValueError("signal clips; normalize it before writing")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, signal.astype(np.float32), rate, subtype=subtype)


def make_loop(signal: np.ndarray, length: float, fade: float, rate: int) -> np.ndarray:
    """Crossfade the rendered tail into the head with an equal-power ramp."""
    count = samples(length, rate)
    fade_count = samples(fade, rate)
    if fade_count <= 0 or fade_count >= count:
        raise ValueError(f"fade must be inside (0, {length}), got {fade}")
    if signal.size < count + fade_count:
        raise ValueError(
            f"loop needs {count + fade_count} samples (length + fade), got {signal.size}"
        )
    looped = signal[:count].copy()
    tail = signal[count : count + fade_count]
    ramp = np.linspace(0.0, np.pi / 2.0, fade_count)
    looped[:fade_count] = tail * np.sin(ramp) + looped[:fade_count] * np.cos(ramp)
    return looped


def rotate_to_quiet(signal: np.ndarray, window: float, rate: int) -> np.ndarray:
    """Move the quietest window to the start; a valid loop stays valid."""
    window_count = samples(window, rate)
    if window_count <= 0 or window_count >= signal.size:
        raise ValueError(f"window must be inside the signal, got {window}s")
    best_start = 0
    best_energy = float("inf")
    for start in range(0, signal.size - window_count + 1, window_count):
        chunk = signal[start : start + window_count]
        energy = float(np.mean(chunk * chunk))
        if energy < best_energy:
            best_energy = energy
            best_start = start
    return np.roll(signal, -best_start)


def verify_audio(
    path: Path,
    rate: int,
    channels: int,
    subtype: str,
    peak_min: float,
    peak_max: float,
    duration_min: float,
    duration_max: float,
    seam_max: float | None,
    edge_max: float | None,
) -> dict:
    if not path.exists():
        raise AudioCheckError(f"audio missing: {path}")
    info = sf.info(path)
    if info.samplerate != rate:
        raise AudioCheckError(f"{path}: samplerate {info.samplerate}, expected {rate}")
    if info.channels != channels:
        raise AudioCheckError(f"{path}: {info.channels} channels, expected {channels}")
    if info.subtype != subtype:
        raise AudioCheckError(f"{path}: subtype {info.subtype}, expected {subtype}")

    data, measured_rate = sf.read(path, dtype="float64", always_2d=False)
    if data.ndim != 1:
        raise AudioCheckError(f"{path}: expected mono samples, got shape {data.shape}")
    duration = data.size / measured_rate
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data * data)))
    if not peak_min <= peak <= peak_max:
        raise AudioCheckError(f"{path}: peak {peak:.4f} outside [{peak_min}, {peak_max}]")
    if not duration_min <= duration <= duration_max:
        raise AudioCheckError(f"{path}: duration {duration:.4f}s outside [{duration_min}, {duration_max}]")

    seam = float(abs(data[0] - data[-1]))
    if seam_max is not None and seam > seam_max:
        raise AudioCheckError(f"{path}: loop seam {seam:.5f} exceeds {seam_max}")

    # One-shot clips must start and end near silence; a loop may start at any
    # phase as long as its seam is continuous.
    edge_step = max(float(abs(data[0])), float(abs(data[-1])))
    if edge_max is not None and edge_step > edge_max:
        raise AudioCheckError(f"{path}: boundary amplitude {edge_step:.5f} exceeds {edge_max}")
    return {
        "path": str(path),
        "duration": round(duration, 4),
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "seam": round(seam, 6),
        "edge_step": round(edge_step, 6),
    }
