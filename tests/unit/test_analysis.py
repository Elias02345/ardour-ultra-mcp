import math

import numpy as np
import pytest
import soundfile as sf

from ardour_ultra_mcp.analysis.audio import analyze, compare
from ardour_ultra_mcp.models.base import DomainError


def test_calibrated_sine_peak_rms_loudness_spectrum_and_stereo(tmp_path):
    rate = 48000
    t = np.arange(rate * 2) / rate
    mono = 0.5 * np.sin(2 * np.pi * 1000 * t)
    path = tmp_path / "sine.wav"
    sf.write(path, np.column_stack([mono, mono]), rate, subtype="FLOAT")
    result = analyze(path)
    assert result["peak_dbfs"] == pytest.approx(20 * math.log10(0.5), abs=0.0001)
    assert result["rms_dbfs"] == pytest.approx(20 * math.log10(0.5 / math.sqrt(2)), abs=0.0001)
    assert result["crest_factor_db"] == pytest.approx(3.0103, abs=0.0001)
    assert result["integrated_lufs"] == pytest.approx(-6.04, abs=0.1)
    assert result["spectrum"]["centroid_hz"] == pytest.approx(1000, abs=1)
    assert result["stereo"]["phase_correlation"] == pytest.approx(1)
    assert result["samples_at_or_above_full_scale"] == 0
    assert result["estimated_true_peak_dbtp"] >= result["peak_dbfs"]


def test_silence_and_short_duration_no_fake_loudness(tmp_path):
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros(4800), 48000)
    result = analyze(path)
    assert result["peak_dbfs"] is None and result["integrated_lufs"] is None
    assert result["silence_seconds"] == 0.1 and result["warnings"]
    sf.write(path, np.ones(4800) * 0.5, 48000, subtype="FLOAT")
    assert analyze(path)["integrated_lufs"] is None


def test_anti_phase_and_known_level_difference(tmp_path):
    rate = 48000
    v = 0.25 * np.sin(2 * np.pi * 220 * np.arange(rate) / rate)
    a, b = tmp_path / "a.wav", tmp_path / "b.wav"
    sf.write(a, np.column_stack([v, -v]), rate, subtype="FLOAT")
    sf.write(b, np.column_stack([v / 2, -v / 2]), rate, subtype="FLOAT")
    first, second = analyze(a), analyze(b)
    assert first["stereo"]["phase_correlation"] == pytest.approx(-1)
    assert first["stereo"]["side_to_mid_ratio"] is None
    result = compare(first, second)
    assert result["delta_second_minus_first"]["peak_dbfs"] == pytest.approx(-6.0206, abs=0.001)
    assert result["delta_second_minus_first"]["integrated_lufs"] == pytest.approx(-6.0206, abs=0.01)


def test_fullscale_count_and_fail_closed_limits(tmp_path):
    path = tmp_path / "clip.wav"
    sf.write(path, np.ones(48000) * 1.1, 48000, subtype="FLOAT")
    assert analyze(path)["samples_at_or_above_full_scale"] == 48000
    with pytest.raises(DomainError):
        analyze(path, max_seconds=0.5)
    sf.write(path, np.zeros((4800, 3)), 48000)
    with pytest.raises(DomainError):
        analyze(path)
    sf.write(path, np.array([np.nan, 1]), 48000, subtype="FLOAT")
    with pytest.raises(DomainError):
        analyze(path)


async def test_low_sample_rate_spectrum_has_valid_available_bands(tmp_path):
    import numpy as np
    import soundfile as sf

    from ardour_ultra_mcp.analysis.audio import analyze

    rate = 8000
    path = tmp_path / "low-rate.wav"
    sf.write(path, 0.25 * np.sin(2 * np.pi * 1000 * np.arange(rate) / rate), rate)
    result = analyze(path, 600)
    assert all(0 <= b["low_hz"] < b["high_hz"] <= rate / 2 for b in result["spectrum"]["bands"])
    assert result["spectrum"]["bands"][-1]["high_hz"] == 4000
    assert "sample peak" in result["silence_method"]
