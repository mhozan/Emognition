# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Before and after calibration, clip by clip: the numbers behind the charts.

The Loudness & trim tab plots five quantities for every clip, as recorded and
as calibrated: duration, the silence before and after the speech, loudness and
peak level. Before anything is written the "after" values are *predicted* from
the plan (:func:`before_after` with the plan alone); once the calibrated files
exist they are *measured* from those files (:func:`measure_written`), so the
chart shows what was really written, frame quantisation and all.

How the prediction works -- the same arithmetic :func:`.preprocess.apply_plan`
does: trimming keeps ``[onset - pad, offset + pad]`` clamped to the file, so the
silence left before the speech is ``min(onset, pad)`` and after it
``min(duration - offset, pad)``; the gain moves loudness and peak by the same
number of dB, less where the peak ceiling caps it.
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from .endpoints import detect_endpoints
from .loudness import NormalizationMethod, measure
from .preprocess import BatchPlan

UNITS: dict[NormalizationMethod, str] = {
    NormalizationMethod.LUFS: "LUFS",
    NormalizationMethod.RMS: "dBFS",
    NormalizationMethod.PEAK: "dBFS",
}
TITLES: dict[NormalizationMethod, str] = {
    NormalizationMethod.LUFS: "Loudness",
    NormalizationMethod.RMS: "RMS level",
    NormalizationMethod.PEAK: "Peak level",
}


def in_sentence(title: str) -> str:
    """A panel title inside a sentence: "Loudness" -> "loudness"; "RMS level" keeps its capitals."""
    first = title.split(" ", 1)[0]
    return title if first.isupper() else title[:1].lower() + title[1:]


@dataclass(frozen=True, slots=True)
class Written:
    """One calibrated file, measured after it was written."""

    filename: str
    duration: float
    onset_s: float
    offset_s: float
    loudness_db: float      # in the plan's method's units
    peak_db: float


def measure_written(paths: Sequence[str], method: NormalizationMethod,
                    progress: Callable[[int, int], None] | None = None) -> list[Written]:
    """Measure the calibrated files the way the plan measured the originals."""
    import soundfile as sf

    out: list[Written] = []
    for path in paths:
        data, rate = sf.read(path, always_2d=True)
        onset, offset = detect_endpoints(data, rate)
        peak = float(np.max(np.abs(data))) if data.size else 0.0
        out.append(Written(
            filename=os.path.basename(path),
            duration=data.shape[0] / rate,
            onset_s=onset,
            offset_s=offset,
            loudness_db=measure(data, rate, method),
            peak_db=20.0 * math.log10(max(peak, 1e-12)),
        ))
        if progress is not None:
            progress(len(out), len(paths))
    return out


@dataclass(frozen=True, slots=True)
class Metric:
    """One chart panel: a quantity for every clip, as recorded and as calibrated."""

    key: str
    title: str
    unit: str
    names: tuple[str, ...]
    before: tuple[float, ...]
    after: tuple[float, ...]
    reference: float | None = None    # the target, ceiling or padding line
    reference_label: str = ""
    limited: tuple[bool, ...] = ()    # clips the peak ceiling held below the target

    @staticmethod
    def span(values: Sequence[float]) -> tuple[float, float]:
        return (min(values), max(values)) if values else (0.0, 0.0)

    @property
    def spread_before(self) -> float:
        lo, hi = self.span(self.before)
        return hi - lo

    @property
    def spread_after(self) -> float:
        lo, hi = self.span(self.after)
        return hi - lo


def before_after(plan: BatchPlan, written: Sequence[Written] | None = None) -> list[Metric]:
    """The panels for *plan*: "after" predicted, or measured when *written* is given."""
    clips = plan.clips
    names = tuple(c.filename for c in clips)
    gains = [plan.gain_applied_db(c) for c in clips]
    if written is not None:
        by_name = {w.filename: w for w in written}
        got = [by_name.get(c.filename) for c in clips]
        if any(w is None for w in got):
            raise ValueError("the written folder is missing some of the planned files")
    else:
        got = None
    pad_ms = plan.pad_s * 1000.0
    unit = UNITS[plan.method]

    def after(predicted, measured):
        return tuple(measured(w) for w in got) if got is not None else tuple(predicted)

    metrics = [
        Metric(
            "duration", "Duration", "s", names,
            tuple(c.orig_duration for c in clips),
            after((c.new_duration for c in clips), lambda w: w.duration)),
        Metric(
            "lead", "Silence before speech", "ms", names,
            tuple(c.onset_s * 1000.0 for c in clips),
            after((min(c.onset_s, c.pad_s) * 1000.0 for c in clips),
                  lambda w: w.onset_s * 1000.0),
            reference=pad_ms, reference_label=f"pad {pad_ms:.0f} ms"),
        Metric(
            "tail", "Silence after speech", "ms", names,
            tuple((c.orig_duration - c.offset_s) * 1000.0 for c in clips),
            after((min(c.orig_duration - c.offset_s, c.pad_s) * 1000.0 for c in clips),
                  lambda w: (w.duration - w.offset_s) * 1000.0),
            reference=pad_ms, reference_label=f"pad {pad_ms:.0f} ms"),
        Metric(
            "loudness", TITLES[plan.method], unit, names,
            tuple(c.measured_db for c in clips),
            after((c.measured_db + g for c, g in zip(clips, gains)), lambda w: w.loudness_db),
            reference=plan.target_db, reference_label=f"target {plan.target_db:g}",
            limited=tuple(c.will_limit for c in clips)),
    ]
    if plan.method is not NormalizationMethod.PEAK:   # for peak, loudness *is* the peak
        metrics.append(Metric(
            "peak", "Peak level", "dBFS", names,
            tuple(c.peak_db for c in clips),
            after((c.peak_db + g for c, g in zip(clips, gains)), lambda w: w.peak_db),
            reference=plan.ceiling_db, reference_label=f"ceiling {plan.ceiling_db:g}",
            limited=tuple(c.will_limit for c in clips)))
    return metrics
