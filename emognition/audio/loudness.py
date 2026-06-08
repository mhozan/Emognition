# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Measuring and adjusting clip loudness.

The trick that keeps this simple: we express **every** loudness metric in
decibels, so normalisation is always the same one-liner --

    gain_dB = target_dB - measured_dB

regardless of whether we're matching perceived loudness (LUFS), RMS, or peak.

* **LUFS** (the default, ``pyloudnorm`` / ITU-R BS.1770) is *perceived* loudness:
  it K-weights the spectrum and gates out silence, so two clips at the same LUFS
  genuinely *sound* equally loud -- which is what we want participants to hear.
* **RMS (dBFS)** and **peak (dBFS)** are simpler energy/level measures, offered as
  options (RMS ~ what the original did).

After applying gain we respect a peak **ceiling** (default -1 dBFS) so the result
can't clip; if hitting the loudness target would clip, we back the gain off and
flag the clip as limited.
"""

from __future__ import annotations

import math
from enum import Enum

import numpy as np
import pyloudnorm as pyln

# A floor so log10(0) on a silent clip yields a very negative dB, not -inf/NaN.
_EPS = 1e-12


class NormalizationMethod(Enum):
    """How to equalise loudness across clips."""

    LUFS = "lufs"   # perceived loudness (ITU-R BS.1770) -- recommended default
    RMS = "rms"     # root-mean-square level in dBFS
    PEAK = "peak"   # peak level in dBFS


# Sensible default target (in the metric's dB units) for each method.
DEFAULT_TARGET_DB: dict[NormalizationMethod, float] = {
    NormalizationMethod.LUFS: -23.0,   # EBU R128 / broadcast
    NormalizationMethod.RMS: -23.0,    # dBFS RMS
    NormalizationMethod.PEAK: -1.0,    # dBFS peak (just below full scale)
}

# Don't let normalised audio exceed this peak (dBFS): guards against clipping.
DEFAULT_CEILING_DB = -1.0


def to_mono(samples: np.ndarray) -> np.ndarray:
    """Collapse (n, channels) to mono by averaging; pass (n,) through."""
    return samples if samples.ndim == 1 else samples.mean(axis=1)


def measure(samples: np.ndarray, rate: int, method: NormalizationMethod) -> float:
    """Measure a clip's loudness in the metric's dB units.

    Returns LUFS for LUFS, dBFS-RMS for RMS, dBFS-peak for PEAK. A silent clip
    yields a large negative number rather than -inf.
    """
    if method is NormalizationMethod.LUFS:
        # pyloudnorm accepts (n,) or (n, channels); it gates silence internally.
        # Clips shorter than one BS.1770 block (~400 ms) can't be measured -> fall
        # back to a very-quiet sentinel rather than crashing.
        try:
            loudness = pyln.Meter(rate).integrated_loudness(samples)
        except (ValueError, IndexError):
            return -120.0
        return float(loudness) if math.isfinite(loudness) else -120.0
    mono = to_mono(samples)
    if method is NormalizationMethod.RMS:
        rms = float(np.sqrt(np.mean(mono ** 2)))
        return 20.0 * math.log10(max(rms, _EPS))
    # PEAK
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    return 20.0 * math.log10(max(peak, _EPS))


def gain_db_to_target(
    samples: np.ndarray,
    rate: int,
    method: NormalizationMethod,
    target_db: float,
) -> float:
    """Gain (dB) needed to bring *samples* to *target_db* under *method*."""
    return target_db - measure(samples, rate, method)


def apply_gain(
    samples: np.ndarray,
    gain_db: float,
    ceiling_db: float = DEFAULT_CEILING_DB,
) -> tuple[np.ndarray, bool]:
    """Apply *gain_db*, then enforce a peak ceiling. Returns (audio, was_limited).

    If the requested gain would push the peak above ``ceiling_db``, the gain is
    reduced so the peak sits exactly at the ceiling, and ``was_limited`` is True
    (the loudness target wasn't fully reached, to avoid clipping).
    """
    out = samples * (10.0 ** (gain_db / 20.0))
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    ceiling = 10.0 ** (ceiling_db / 20.0)
    if peak > ceiling:
        out = out * (ceiling / peak)
        return out, True
    return out, False
