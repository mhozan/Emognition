# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Batch preprocessing: plan first, then apply.

The two-step shape is deliberate. :func:`plan_batch` only *reads* the files and
returns a :class:`BatchPlan` describing what *would* change per clip (how much
silence would be trimmed, what loudness gain would be applied). The Calibration
UI shows that for confirmation -- so a set that's already clean (tiny trims, near-
zero gain; see :meth:`BatchPlan.is_minor`) can be skipped. Only :func:`apply_plan`
writes anything, and it writes to a *new* folder; originals are never touched.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

import soundfile as sf

from .endpoints import detect_endpoints, trim_samples
from .loudness import (
    DEFAULT_CEILING_DB,
    DEFAULT_TARGET_DB,
    NormalizationMethod,
    apply_gain,
    measure,
)


@dataclass(frozen=True, slots=True)
class ClipPlan:
    """What preprocessing would do to one clip (no audio written yet)."""

    path: str
    filename: str
    rate: int
    orig_duration: float
    onset_s: float
    offset_s: float
    pad_s: float
    new_duration: float
    lead_trim_s: float       # silence removed from the start
    tail_trim_s: float       # silence removed from the end
    measured_db: float       # loudness of the trimmed clip (method units)
    gain_db: float           # gain that would be applied to hit the target
    will_limit: bool         # True if peak-ceiling would cap the gain (clip-safe)

    @property
    def trim_ms(self) -> float:
        """Total silence that would be removed, in milliseconds."""
        return (self.lead_trim_s + self.tail_trim_s) * 1000.0


@dataclass(frozen=True, slots=True)
class BatchPlan:
    """The full plan for a folder of clips, plus the settings used."""

    clips: list[ClipPlan]
    method: NormalizationMethod
    target_db: float
    ceiling_db: float
    pad_s: float
    out_dir: str

    @property
    def max_trim_ms(self) -> float:
        return max((c.trim_ms for c in self.clips), default=0.0)

    @property
    def max_abs_gain_db(self) -> float:
        return max((abs(c.gain_db) for c in self.clips), default=0.0)

    @property
    def loudness_spread_db(self) -> float:
        """Range of measured loudness across clips (how uneven the set is)."""
        vals = [c.measured_db for c in self.clips]
        return (max(vals) - min(vals)) if vals else 0.0

    def is_minor(self, *, min_trim_ms: float = 30.0, min_gain_db: float = 1.0) -> bool:
        """True if every change is tiny -- the experimenter can safely skip.

        Lets the confirmation step say "these files look already calibrated".
        """
        return self.max_trim_ms < min_trim_ms and self.max_abs_gain_db < min_gain_db


def plan_batch(
    paths: Sequence[str],
    out_dir: str,
    *,
    method: NormalizationMethod = NormalizationMethod.LUFS,
    target_db: float | None = None,
    threshold_db: float = -40.0,
    pad_s: float = 0.10,
    ceiling_db: float = DEFAULT_CEILING_DB,
) -> BatchPlan:
    """Analyse every clip and return what preprocessing *would* do (no writes)."""
    if target_db is None:
        target_db = DEFAULT_TARGET_DB[method]

    clips: list[ClipPlan] = []
    for path in paths:
        data, rate = sf.read(path)
        orig_duration = data.shape[0] / rate
        onset_s, offset_s = detect_endpoints(data, rate, threshold_db=threshold_db)
        trimmed = trim_samples(data, rate, onset_s, offset_s, pad_s)
        new_duration = trimmed.shape[0] / rate

        measured_db = measure(trimmed, rate, method)
        gain_db = target_db - measured_db
        _, will_limit = apply_gain(trimmed, gain_db, ceiling_db)

        lead_trim_s = max(0.0, onset_s - pad_s)
        tail_trim_s = max(0.0, orig_duration - (offset_s + pad_s))
        clips.append(ClipPlan(
            path=path,
            filename=os.path.basename(path),
            rate=rate,
            orig_duration=orig_duration,
            onset_s=onset_s,
            offset_s=offset_s,
            pad_s=pad_s,
            new_duration=new_duration,
            lead_trim_s=lead_trim_s,
            tail_trim_s=tail_trim_s,
            measured_db=measured_db,
            gain_db=gain_db,
            will_limit=will_limit,
        ))

    return BatchPlan(
        clips=clips, method=method, target_db=target_db,
        ceiling_db=ceiling_db, pad_s=pad_s, out_dir=out_dir,
    )


def apply_plan(
    plan: BatchPlan,
    *,
    trim: bool = True,
    normalize: bool = True,
) -> list[str]:
    """Write the calibrated clips to ``plan.out_dir``; return the written paths.

    Originals are read but never modified. Output keeps each source file's name
    and audio subtype (e.g. 16-bit PCM).
    """
    os.makedirs(plan.out_dir, exist_ok=True)
    written: list[str] = []
    for clip in plan.clips:
        data, rate = sf.read(clip.path)
        subtype = sf.info(clip.path).subtype  # preserve e.g. PCM_16
        if trim:
            data = trim_samples(data, rate, clip.onset_s, clip.offset_s, clip.pad_s)
        if normalize:
            data, _ = apply_gain(data, clip.gain_db, plan.ceiling_db)
        out_path = os.path.join(plan.out_dir, clip.filename)
        sf.write(out_path, data, rate, subtype=subtype)
        written.append(out_path)
    return written
