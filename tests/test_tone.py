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
    rate, peak = 44100, 0.2 * math.sqrt(2)
    tone = calibration_tone(rms=0.2, seconds=0.5, rate=rate, hann_ms=100.0)
    # The first 10 ms of a 1 kHz sine hold 10 full cycles; with a 50 ms Hann
    # fade-in they must stay below sin^2(pi*0.1) ~ 0.1 of the peak (an unfaded
    # tone reaches the full peak there). The old check, tone[0] ~ 0, passed even
    # without a fade, because sin(0) = 0.
    head = np.abs(tone[: rate // 100])
    assert head.max() < 0.12 * peak
    assert np.max(np.abs(tone)) > 0.99 * peak        # full amplitude in the middle
    assert np.abs(tone[-rate // 100:]).max() < 0.12 * peak   # and faded out


def test_short_tone_gets_a_proportionally_short_fade():
    rate, peak = 44100, 0.1 * math.sqrt(2)
    tone = calibration_tone(rms=0.1, seconds=0.05, rate=rate, hann_ms=500.0)  # 50 ms tone, 500 ms window
    assert np.max(np.abs(tone)) > 0.9 * peak         # still reaches (almost) full level


@pytest.mark.parametrize("rms, seconds", [(0.8, 1.0), (0.0, 1.0), (0.1, 0.0), (0.1, 301.0)])
def test_tone_rejects_clipping_or_absurd_settings(rms, seconds):
    with pytest.raises(ValueError):
        calibration_tone(rms=rms, seconds=seconds)


def test_average_rms_is_per_channel(tmp_path):
    import soundfile as sf

    left = 0.2 * np.ones(1000)
    sf.write(str(tmp_path / "s.wav"), np.stack([left, -left], axis=1), 8000, subtype="FLOAT")
    # Averaging the channels first would give 0 for this out-of-phase file.
    assert average_rms([str(tmp_path / "s.wav")]) == pytest.approx(0.2, abs=1e-6)


def test_average_rms_of_bundled_clips_is_positive():
    paths = [
        os.path.join(ASSETS_AUDIO, f)
        for f in sorted(os.listdir(ASSETS_AUDIO)) if f.endswith(".wav")
    ]
    rms = average_rms(paths)
    assert 0.0 < rms < 1.0


def test_tone_plays_stereo_at_the_session_volume(monkeypatch):
    """The tone takes the clips' path -- one stereo stream, at --volume -- so a level
    set with it is the level the clips are heard at (it used to play mono at 1.0)."""
    import sys
    import types

    from emognition import app, runtime

    made = []

    class FakeSound:
        def __init__(self, value, stereo=None, **kwargs):
            self.stereo, self.volume, self.played = stereo, 1.0, False
            made.append(self)

        def play(self):
            self.played = True

        def stop(self):
            pass

    fake = types.ModuleType("psychopy")
    fake.sound = types.SimpleNamespace(Sound=FakeSound)
    fake.core = types.SimpleNamespace(wait=lambda seconds: None, quit=lambda: None)
    monkeypatch.setitem(sys.modules, "psychopy", fake)
    monkeypatch.setattr(runtime, "bootstrap", lambda: None)
    monkeypatch.setattr(runtime, "ptb_audio_problem", lambda *a, **k: None)
    with pytest.raises(SystemExit) as exited:
        app.main(["--play-tone", "--tone-rms", "0.05", "--tone-seconds", "2", "--volume", "0.6"])
    assert exited.value.code == 0
    (snd,) = made
    assert snd.stereo is True and snd.volume == pytest.approx(0.6) and snd.played
