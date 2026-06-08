# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for audio preprocessing (loudness, endpoints, plan/apply).

All file I/O, no audio device or display -- safe and fast in CI.
"""

import math
import os

import numpy as np
import pytest

from emognition.audio import (
    NormalizationMethod,
    apply_gain,
    detect_endpoints,
    measure,
    plan_batch,
    apply_plan,
    trim_samples,
)
from emognition.audio.loudness import measure as measure_loudness

RATE = 16000
ASSETS_AUDIO = os.path.join(os.path.dirname(__file__), os.pardir, "assets", "audio")


def _sine(amp, dur, freq=440.0, rate=RATE):
    t = np.arange(int(dur * rate)) / rate
    return amp * np.sin(2 * np.pi * freq * t)


# -- loudness measurement --------------------------------------------------

def test_rms_dbfs_of_full_scale_sine():
    # A full-scale sine has RMS = 1/sqrt(2) -> about -3.01 dBFS.
    sig = _sine(1.0, 1.0)
    assert measure(sig, RATE, NormalizationMethod.RMS) == pytest.approx(-3.01, abs=0.1)


def test_peak_dbfs():
    sig = _sine(0.5, 1.0)
    assert measure(sig, RATE, NormalizationMethod.PEAK) == pytest.approx(-6.02, abs=0.1)


# -- gain + ceiling --------------------------------------------------------

def test_apply_gain_without_clipping():
    sig = _sine(0.1, 0.2)             # peak 0.1
    out, limited = apply_gain(sig, gain_db=12.0, ceiling_db=-1.0)
    assert not limited
    assert float(np.max(np.abs(out))) == pytest.approx(0.1 * 10 ** (12 / 20), abs=1e-3)


def test_apply_gain_respects_ceiling():
    sig = _sine(0.1, 0.2)             # peak 0.1; +30 dB would clip
    out, limited = apply_gain(sig, gain_db=30.0, ceiling_db=-1.0)
    assert limited
    ceiling = 10 ** (-1.0 / 20)
    assert float(np.max(np.abs(out))) == pytest.approx(ceiling, abs=1e-3)


# -- endpoint detection ----------------------------------------------------

def test_detect_endpoints_finds_the_burst():
    # 0.5 s silence | 0.5 s tone | 0.5 s silence
    sig = np.concatenate([_sine(0.0, 0.5), _sine(0.5, 0.5), _sine(0.0, 0.5)])
    onset, offset = detect_endpoints(sig, RATE, threshold_db=-40.0)
    assert onset == pytest.approx(0.5, abs=0.05)
    assert offset == pytest.approx(1.0, abs=0.06)


def test_silence_is_not_trimmed():
    sig = _sine(0.0, 1.0)            # pure silence
    onset, offset = detect_endpoints(sig, RATE)
    assert (onset, offset) == (0.0, pytest.approx(1.0))


def test_trim_samples_lengths():
    sig = _sine(0.3, 1.0)
    trimmed = trim_samples(sig, RATE, onset_s=0.4, offset_s=0.6, pad_s=0.05)
    # span (0.35 .. 0.65) = 0.30 s
    assert len(trimmed) == pytest.approx(int(0.30 * RATE), abs=2)


# -- batch plan + apply on the real bundled clips --------------------------

def test_plan_and_apply_on_bundled_clips(tmp_path):
    paths = sorted(
        os.path.join(ASSETS_AUDIO, f)
        for f in os.listdir(ASSETS_AUDIO) if f.endswith(".wav")
    )
    out_dir = str(tmp_path / "audio_calibrated")
    plan = plan_batch(paths, out_dir, method=NormalizationMethod.LUFS, target_db=-23.0)

    assert len(plan.clips) == 10
    # Every clip carries an onset/offset and a finite gain.
    for c in plan.clips:
        assert 0.0 <= c.onset_s <= c.offset_s <= c.orig_duration
        assert math.isfinite(c.gain_db)

    written = apply_plan(plan)
    assert len(written) == 10
    assert all(os.path.exists(p) for p in written)

    # A normalized clip that wasn't peak-limited should sit near the target.
    import soundfile as sf
    for c, p in zip(plan.clips, written):
        if not c.will_limit:
            data, rate = sf.read(p)
            assert measure_loudness(data, rate, NormalizationMethod.LUFS) == pytest.approx(
                -23.0, abs=1.5
            )
            break
