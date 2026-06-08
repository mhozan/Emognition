# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Finding where speech starts and ends in a clip (and trimming to it).

Why this matters for the science: reaction time is most meaningful measured from
the **audio offset** -- the instant the participant has heard the whole word. If a
recording has a second of trailing silence, "offset" is a second too late and RTs
are inflated/unreliable. So we detect the real speech onset/offset and trim.

Method (simple, robust, dependency-free): slide a short window over the signal,
take each frame's RMS, and call a frame "speech" if it's within ``threshold_db``
of the loudest frame. The onset is the first such frame, the offset the last.
A relative threshold (vs. the clip's own peak) adapts to each recording's level.
"""

from __future__ import annotations

import math

import numpy as np

from .loudness import to_mono


def detect_endpoints(
    samples: np.ndarray,
    rate: int,
    *,
    threshold_db: float = -40.0,
    frame_ms: float = 20.0,
    hop_ms: float = 10.0,
) -> tuple[float, float]:
    """Return ``(onset_s, offset_s)`` -- the speech span within the clip.

    Args:
        samples: Audio, mono or multichannel (analysed in mono).
        rate: Sample rate (Hz).
        threshold_db: A frame counts as speech if its RMS is within this many dB
            of the loudest frame (default -40 dB below peak).
        frame_ms / hop_ms: Analysis window length and step.

    If the clip is effectively silent, returns ``(0.0, duration)`` so nothing is
    trimmed.
    """
    mono = to_mono(samples)
    n = mono.shape[0]
    duration = n / rate
    if n == 0:
        return 0.0, 0.0

    frame = max(1, int(rate * frame_ms / 1000.0))
    hop = max(1, int(rate * hop_ms / 1000.0))
    if n < frame:
        return 0.0, duration

    # Per-frame RMS.
    starts = range(0, n - frame + 1, hop)
    energies = np.array([
        math.sqrt(float(np.mean(mono[s:s + frame] ** 2))) for s in starts
    ])
    peak = float(energies.max()) if energies.size else 0.0
    if peak <= 0.0:
        return 0.0, duration

    threshold = peak * (10.0 ** (threshold_db / 20.0))
    above = np.flatnonzero(energies >= threshold)
    if above.size == 0:
        return 0.0, duration

    first_frame, last_frame = int(above[0]), int(above[-1])
    onset_s = (first_frame * hop) / rate
    # offset is the END of the last speech frame.
    offset_s = min(duration, (last_frame * hop + frame) / rate)
    return onset_s, offset_s


def trim_samples(
    samples: np.ndarray,
    rate: int,
    onset_s: float,
    offset_s: float,
    pad_s: float = 0.04,
) -> np.ndarray:
    """Return the clip cut to ``[onset_s - pad, offset_s + pad]`` (clamped).

    The padding keeps a little air around the speech so soft onsets/offsets
    (e.g. fricatives) aren't clipped. Works for mono and multichannel.
    """
    n = samples.shape[0]
    start = max(0, int(round((onset_s - pad_s) * rate)))
    end = min(n, int(round((offset_s + pad_s) * rate)))
    if end <= start:
        return samples  # degenerate; leave untouched
    return samples[start:end]
