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

# A sine's peak is sqrt(2) x its RMS, so above this RMS the tone would clip at
# full scale (and a clipped calibration tone is both wrong and needlessly loud).
MAX_TONE_RMS = 1.0 / math.sqrt(2.0)
# The Calibration window offers up to 5 minutes; longer is almost certainly a typo.
MAX_TONE_SECONDS = 300.0


def average_rms(paths: Sequence[str]) -> float:
    """Mean linear RMS across the given audio files, 0.0 if none.

    Each file's level is the mean of its *per-channel* RMS -- the level each ear
    hears -- as the original computed it per channel. (Averaging the channels
    first lowers the level of any stereo file whose channels differ.)
    """
    rmss: list[float] = []
    for path in paths:
        data, _ = sf.read(path, always_2d=True)       # (samples, channels)
        if data.size:
            per_channel = np.sqrt(np.mean(data.astype(np.float64) ** 2, axis=0))
            rmss.append(float(per_channel.mean()))
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
        hann_ms: Total Hann window length; half fades in, half fades out. A tone
            shorter than the window gets a proportionally shorter fade.

    Raises:
        ValueError: if *rms* would clip (> 1/sqrt(2)) or isn't positive, or if
            *seconds* is not in (0, 300].
    """
    if not 0.0 < rms <= MAX_TONE_RMS:
        raise ValueError(f"tone RMS must be in (0, {MAX_TONE_RMS:.3f}] to avoid clipping, got {rms}")
    if not 0.0 < seconds <= MAX_TONE_SECONDS:
        raise ValueError(f"tone length must be in (0, {MAX_TONE_SECONDS:g}] seconds, got {seconds}")
    n = max(1, int(seconds * rate))
    t = np.arange(n) / rate
    tone = math.sqrt(2.0) * rms * np.sin(2.0 * math.pi * freq * t)

    # Apply a Hann (raised-cosine) fade to each end, like the original.
    # (A tone shorter than the window used to take the first samples of the
    # full-length window, so it never rose above half amplitude.)
    nhann = min(int(hann_ms * rate / 1000.0), n)
    if nhann > 1:
        window = np.sin(np.pi * np.arange(nhann) / (nhann - 1)) ** 2
        half = nhann // 2
        if half > 0:
            tone[:half] *= window[:half]
            tone[-half:] *= window[-half:]
    return tone
