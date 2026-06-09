# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the SPL calibration tone (no audio playback)."""

import math
import os

import numpy as np
import pytest

from emognition.audio import average_rms, calibration_tone

ASSETS_AUDIO = os.path.join(os.path.dirname(__file__), os.pardir, "assets", "audio")


def test_tone_length_and_rms():
    rate = 44100
    tone = calibration_tone(rms=0.1, seconds=1.0, rate=rate, hann_ms=50.0)
    assert len(tone) == rate
    # Measure RMS over the un-faded middle second-half; should match the target.
    mid = tone[rate // 4: 3 * rate // 4]
    assert math.sqrt(float(np.mean(mid ** 2))) == pytest.approx(0.1, abs=0.005)


def test_tone_is_hann_faded_at_the_ends():
    tone = calibration_tone(rms=0.2, seconds=0.5, rate=44100, hann_ms=100.0)
    # The very first sample is faded to (near) zero, unlike the middle.
    assert abs(tone[0]) < 0.02
    assert np.max(np.abs(tone)) > 0.2  # full amplitude reached in the middle


def test_average_rms_of_bundled_clips_is_positive():
    paths = [
        os.path.join(ASSETS_AUDIO, f)
        for f in sorted(os.listdir(ASSETS_AUDIO)) if f.endswith(".wav")
    ]
    rms = average_rms(paths)
    assert 0.0 < rms < 1.0
