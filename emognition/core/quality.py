# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Reaction-time quality control: flag implausible trials.

Reaction-time data is noisy at both ends. Two cleaning steps are near-universal
in the literature, and we make them explicit and auditable here:

* **Anticipatory** -- a response so fast (default < 150 ms after the clip's
  *onset*) that the participant can't actually have processed the stimulus; it's
  a guess or an accidental press.
* **Slow outlier** -- a response far slower than the rest. We use a *robust*
  rule (median + k x 1.4826 x MAD, the median absolute deviation) rather than
  mean + k x SD, because a single extreme value inflates the ordinary mean/SD
  enough to hide itself ("masking"). The robust estimator isn't fooled by the
  very point we're trying to catch.

We *flag* rather than silently drop, so nothing is hidden: the per-trial report
shows every flag, and only the **reaction-time means** exclude flagged trials.
Accuracy and the confusion matrix always use every answered trial -- a slow or
anticipatory answer is still right or wrong.

The exclusion is implemented by :func:`scrub_flagged_rts`, which simply nulls the
RT of a flagged trial. The scoring code already ignores ``None`` RTs, so the
means drop those trials with no special-casing.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import replace
from enum import Enum

from .responses import Response

# A response faster than this (from audio onset) is treated as anticipatory.
ANTICIPATORY_THRESHOLD_S = 0.15
# Slow-outlier cutoff, in standard deviations above the mean RT.
DEFAULT_SD_CUTOFF = 3.0


class RtFlag(Enum):
    """Quality verdict for one trial's reaction time."""

    OK = "ok"
    NO_RESPONSE = "no_response"
    ANTICIPATORY = "anticipatory"
    SLOW_OUTLIER = "slow_outlier"

    @property
    def is_excluded(self) -> bool:
        """Whether this flag should be excluded from reaction-time means."""
        return self in (RtFlag.ANTICIPATORY, RtFlag.SLOW_OUTLIER)


def flag_responses(
    responses: Sequence[Response],
    *,
    rt_kind: str = "offset",
    min_onset_rt: float = ANTICIPATORY_THRESHOLD_S,
    sd_cutoff: float = DEFAULT_SD_CUTOFF,
) -> list[RtFlag]:
    """Classify every response's reaction time. Returns one flag per response.

    Args:
        responses: The trials to classify (order preserved in the result).
        rt_kind: Which RT to use for the slow-outlier test ("offset" or "onset").
        min_onset_rt: Onset-relative RT below which a trial is anticipatory.
        sd_cutoff: Slow-outlier threshold, in robust SDs above the median.

    Anticipatory uses the *onset* RT (a fixed perceptual-plausibility floor); the
    slow-outlier test uses ``rt_kind`` with a robust median/MAD estimator, over
    trials not already excluded, and only when there are enough of them (and any
    spread) to judge.
    """
    flags: list[RtFlag] = []
    for r in responses:
        if not r.answered:
            flags.append(RtFlag.NO_RESPONSE)
        elif r.rt_onset is not None and r.rt_onset < min_onset_rt:
            flags.append(RtFlag.ANTICIPATORY)
        else:
            flags.append(RtFlag.OK)

    # Slow-outlier pass over the currently-OK trials, using the chosen RT.
    rt_attr = "rt_onset" if rt_kind == "onset" else "rt_offset"
    eligible = [
        (i, getattr(responses[i], rt_attr))
        for i, f in enumerate(flags)
        if f is RtFlag.OK and getattr(responses[i], rt_attr) is not None
    ]
    if len(eligible) >= 2:
        values = [v for _, v in eligible]
        median = statistics.median(values)
        # MAD = median absolute deviation; x1.4826 makes it a SD-equivalent for
        # normal data. Robust to the very outlier we're hunting (no masking).
        mad = statistics.median([abs(v - median) for v in values])
        robust_sd = 1.4826 * mad
        if robust_sd > 0:
            cutoff = median + sd_cutoff * robust_sd
            for i, v in eligible:
                if v > cutoff:
                    flags[i] = RtFlag.SLOW_OUTLIER
    return flags


def scrub_flagged_rts(
    responses: Sequence[Response],
    flags: Sequence[RtFlag],
) -> list[Response]:
    """Return copies with flagged trials' RTs nulled (so RT means exclude them).

    The participant's response (and thus correctness) is preserved; only
    ``rt_onset``/``rt_offset`` are set to ``None`` for excluded flags. Pass the
    result to :func:`core.summarize` to get RT means that ignore flagged trials.
    """
    out: list[Response] = []
    for r, flag in zip(responses, flags):
        if flag.is_excluded:
            out.append(replace(r, rt_onset=None, rt_offset=None))
        else:
            out.append(r)
    return out
