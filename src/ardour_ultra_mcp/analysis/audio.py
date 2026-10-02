"""Bounded offline numerical analysis. No subjective quality score."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..models.base import DomainError, ErrorCode


def analyze(path: Path, max_seconds: float = 600) -> dict[str, Any]:
    try:
        import numpy as np
        import pyloudnorm as pyln
        import soundfile as sf
        from scipy.signal import resample_poly, welch
    except ImportError as exc:
        raise DomainError(
            ErrorCode.BACKEND_UNSUPPORTED,
            "Optional audio analysis packages are missing.",
            "Install ardour-ultra-mcp[analysis].",
        ) from exc
    try:
        with sf.SoundFile(path) as stream:
            if stream.channels not in {1, 2}:
                raise DomainError(
                    ErrorCode.OPERATION_NOT_SUPPORTED,
                    "Analysis currently supports mono/stereo only.",
                )
            if stream.frames < 1 or stream.samplerate < 8000 or stream.samplerate > 384000:
                raise DomainError(
                    ErrorCode.VALIDATION_ERROR, "Invalid/unsupported audio duration or sample rate."
                )
            if (
                stream.frames / stream.samplerate > max_seconds
                or stream.frames * stream.channels > 32_000_000
            ):
                raise DomainError(
                    ErrorCode.VALIDATION_ERROR,
                    "Analysis exceeds duration/memory bound.",
                    "Render a shorter section; no silent truncation is performed.",
                )
            sample_rate, channels = stream.samplerate, stream.channels
            metadata = {
                "path": str(path),
                "sample_rate_hz": sample_rate,
                "channels": channels,
                "frames": stream.frames,
                "duration_seconds": stream.frames / sample_rate,
                "format": stream.format,
                "subtype": stream.subtype,
            }
            audio = stream.read(dtype="float64", always_2d=True)
    except (OSError, sf.LibsndfileError) as exc:
        raise DomainError(
            ErrorCode.VALIDATION_ERROR, "Audio could not be decoded by libsndfile."
        ) from exc
    if not np.isfinite(audio).all():
        raise DomainError(ErrorCode.VALIDATION_ERROR, "Audio contains NaN or infinity.")
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio * audio)))

    def db(v: float) -> float | None:
        return 20 * math.log10(v) if v > 0 else None

    warnings = []
    lufs = None
    if metadata["duration_seconds"] >= 0.4 and peak > 0:
        measured = float(pyln.Meter(sample_rate).integrated_loudness(audio))
        lufs = measured if math.isfinite(measured) else None
    else:
        warnings.append(
            "Integrated LUFS unavailable for silence or audio shorter than the 400 ms gate."
        )
    true_peak = peak
    # Overlapping context avoids treating each chunk as a zero-padded independent signal.
    for start in range(0, len(audio), 65536):
        end = min(start + 65536, len(audio))
        lo, hi = max(0, start - 64), min(len(audio), end + 64)
        expanded = resample_poly(audio[lo:hi], 4, 1, axis=0)
        true_peak = max(
            true_peak, float(np.max(np.abs(expanded[(start - lo) * 4 : (end - lo) * 4])))
        )
    frequencies, spectrum = welch(audio, sample_rate, nperseg=min(8192, len(audio)), axis=0)
    energy = np.mean(spectrum, axis=1)
    total = float(np.sum(energy))
    bands = []
    for low, high in [(20, 60), (60, 250), (250, 500), (500, 2000), (2000, 6000), (6000, 20000)]:
        power = float(np.sum(energy[(frequencies >= low) & (frequencies < high)]))
        bands.append(
            {
                "low_hz": low,
                "high_hz": min(high, sample_rate / 2),
                "fraction_of_measured_power": power / total if total > 0 else None,
            }
        )
    frame_size = max(1, round(sample_rate * 0.02))
    silent_frames = 0
    for start in range(0, len(audio), frame_size):
        block = audio[start : start + frame_size]
        if float(np.max(np.abs(block))) < 0.001:
            silent_frames += len(block)
    stereo = None
    if channels == 2:
        left, right = audio[:, 0], audio[:, 1]
        lm, rm = left - np.mean(left), right - np.mean(right)
        denominator = float(np.sqrt(np.sum(lm * lm) * np.sum(rm * rm)))
        mid, side = (left + right) / 2, (left - right) / 2
        mid_rms, side_rms = float(np.sqrt(np.mean(mid * mid))), float(np.sqrt(np.mean(side * side)))
        stereo = {
            "phase_correlation": float(np.sum(lm * rm)) / denominator if denominator > 0 else None,
            "mid_rms_dbfs": db(mid_rms),
            "side_rms_dbfs": db(side_rms),
            "side_to_mid_ratio": side_rms / mid_rms if mid_rms > 0 else None,
        }
    return {
        "metadata": metadata,
        "peak_dbfs": db(peak),
        "rms_dbfs": db(rms),
        "crest_factor_db": db(peak / rms) if rms > 0 else None,
        "integrated_lufs": lufs,
        "estimated_true_peak_dbtp": db(true_peak),
        "true_peak_method": "4x scipy polyphase FIR estimate; not certified BS.1770 true peak",
        "samples_at_or_above_full_scale": int(np.count_nonzero(np.abs(audio) >= 1)),
        "full_scale_fraction": float(np.mean(np.abs(audio) >= 1)),
        "dc_offset_per_channel": [float(x) for x in np.mean(audio, axis=0)],
        "silence_seconds": silent_frames / sample_rate,
        "silence_threshold_dbfs": -60,
        "silence_window_seconds": 0.02,
        "spectrum": {
            "method": "Welch mean channel power; fractions include DC/Nyquist in denominator",
            "bands": bands,
            "centroid_hz": float(np.sum(frequencies * energy)) / total if total > 0 else None,
        },
        "stereo": stereo,
        "warnings": warnings,
    }


def compare(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    metrics = [
        "peak_dbfs",
        "rms_dbfs",
        "crest_factor_db",
        "integrated_lufs",
        "estimated_true_peak_dbtp",
        "silence_seconds",
    ]
    return {
        "first": first,
        "second": second,
        "delta_second_minus_first": {
            k: second[k] - first[k] if first[k] is not None and second[k] is not None else None
            for k in metrics
        },
        "same_duration": first["metadata"]["frames"] == second["metadata"]["frames"]
        and first["metadata"]["sample_rate_hz"] == second["metadata"]["sample_rate_hz"],
    }
