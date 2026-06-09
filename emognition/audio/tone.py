# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""SPL calibration tone -- a 1 kHz sine matched to the recordings' loudness.

For setting the physical playback level in a sound booth: play this tone, read
the dB SPL on a sound-level meter, and adjust the amplifier. Because the tone's
RMS equals the recordings' average RMS, calibrating the tone calibrates the
speech. Hann-windowed at both ends so it starts/stops without a click.

Ported from the calibration maths in the original ``calibrationmode.m`` (the sine
is ``sqrt(2) * avg_rms * sin(2*pi*f*t)`` so its RMS == ``avg_rms``).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import soundfile as sf

from .loudness import to_mono


def average_rms(paths: Sequence[str]) -> float:
    """Mean linear RMS across the given audio files (mono), 0.0 if none."""
    rmss: list[float] = []
    for path in paths:
        data, _ = sf.read(path)
        mono = to_mono(data)
        if mono.size:
            rmss.append(float(np.sqrt(np.mean(mono ** 2))))
    return float(np.mean(rmss)) if rmss else 0.0


def calibration_tone(
    rms: float,
    seconds: float,
    *,
    freq: float = 1000.0,
    rate: int = 44100,
    hann_ms: float = 100.0,
) -> np.ndarray:
    """Generate a Hann-windowed sine of RMS ``rms`` (a sine's RMS = amp/sqrt2).

    Args:
        rms: Target RMS amplitude (linear, e.g. the recordings' average RMS).
        seconds: Tone duration.
        freq: Frequency in Hz (1000 Hz is the speech-calibration convention).
        rate: Sample rate.
        hann_ms: Total Hann window length; half fades in, half fades out.
    """
    n = max(1, int(seconds * rate))
    t = np.arange(n) / rate
    tone = math.sqrt(2.0) * rms * np.sin(2.0 * math.pi * freq * t)

    # Apply a Hann (raised-cosine) fade to each end, like the original.
    nhann = int(hann_ms * rate / 1000.0)
    if nhann > 1:
        window = np.sin(np.pi * np.arange(nhann) / (nhann - 1)) ** 2
        half = min(len(window) // 2, n // 2)
        if half > 0:
            tone[:half] *= window[:half]
            tone[-half:] *= window[-half:]
    return tone
