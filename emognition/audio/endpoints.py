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

import numpy as np

from .loudness import to_mono


def frame_rms(mono: np.ndarray, rate: int, frame_ms: float = 20.0,
              hop_ms: float = 10.0) -> tuple[np.ndarray, int, int]:
    """Short-time RMS: one value per *frame_ms* window, every *hop_ms*.

    Returns ``(energies, frame, hop)`` with *frame* and *hop* in samples. This
    is what :func:`detect_endpoints` decides on, so the calibration window
    plots exactly the curve the detector saw.

    Every frame's sum of squares comes from one running sum -- the sum over
    samples ``s .. s + frame - 1`` is ``cum[s + frame - 1] - cum[s - 1]`` -- so
    the cost is one pass over the samples however much the frames overlap (it
    used to be a Python loop over frames: 5x slower on a 2 s clip). The running
    sum is float64 and built in place, so even a long file needs one temporary;
    a rounding residue below zero is clamped.
    """
    frame = max(1, int(rate * frame_ms / 1000.0))
    hop = max(1, int(rate * hop_ms / 1000.0))
    if mono.shape[0] < frame:
        return np.zeros(0), frame, hop
    cum = np.square(mono, dtype=np.float64)
    np.cumsum(cum, out=cum)
    starts = np.arange(0, mono.shape[0] - frame + 1, hop)
    ends = cum[starts + frame - 1]
    begins = np.empty_like(ends)
    begins[0] = 0.0                                      # the first frame starts at sample 0
    begins[1:] = cum[starts[1:] - 1]
    return np.sqrt(np.maximum(ends - begins, 0.0) / frame), frame, hop


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
    energies, frame, hop = frame_rms(mono, rate, frame_ms, hop_ms)
    return endpoints_from_rms(energies, frame, hop, mono.shape[0], rate, threshold_db=threshold_db)


def endpoints_from_rms(
    energies: np.ndarray,
    frame: int,
    hop: int,
    n_samples: int,
    rate: int,
    *,
    threshold_db: float = -40.0,
) -> tuple[float, float]:
    """The speech span from a :func:`frame_rms` curve (the second half of
    :func:`detect_endpoints`, for a caller that has the curve already)."""
    duration = n_samples / rate
    if energies.size == 0:
        return 0.0, duration
    peak = float(energies.max())
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


def speech_span(path: str, **kwargs) -> tuple[float, float]:
    """:func:`detect_endpoints` for a sound file: ``(onset_s, offset_s)`` from its start."""
    import soundfile as sf     # local: keeps `import emognition.audio` light

    samples, rate = sf.read(path, dtype="float32", always_2d=True)
    return detect_endpoints(samples, rate, **kwargs)


def trim_samples(
    samples: np.ndarray,
    rate: int,
    onset_s: float,
    offset_s: float,
    pad_s: float = 0.10,
) -> np.ndarray:
    """Return the clip cut to ``[onset_s - pad, offset_s + pad]`` (clamped).

    100 ms is conservative: enough to protect soft-onset fricatives and
    plosive release bursts without adding perceptible dead air. Works for
    mono and multichannel.
    """
    n = samples.shape[0]
    start = max(0, int(round((onset_s - pad_s) * rate)))
    end = min(n, int(round((offset_s + pad_s) * rate)))
    if end <= start:
        return samples  # degenerate; leave untouched
    return samples[start:end]
