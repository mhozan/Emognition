# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Turning a list of trial responses into the session's scores.

This is the UI-free port of the number-crunching in ``monitorperf.m`` (which, in
the original, was tangled up with drawing the live experimenter window). The two
products feed the Excel/PDF reports directly:

* a **confusion matrix** -- ``matrix[true][responded]``, i.e. rows are the
  emotion that was played and columns are the emotion the participant chose, in
  the canonical Happy / Scared / Neutral / Sad / Angry order; and
* **summary statistics** -- percent-correct, mean reaction time, and mean replays
  broken down per emotion, per speaker gender, and overall (the legacy
  "Percentages" sheet).

Percent-correct for an emotion is ``100 * diagonal / row-sum`` -- correct
responses divided by the number of times that emotion was presented -- exactly as
the original computed ``tabl(i,i)/sum(tabl(i,:))``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .emotions import Emotion, EMOTIONS_IN_ORDER, Gender
from .responses import Response

# Default reaction-time basis for the reported means. The legacy reactiontime.m
# measured from the audio offset, so that is our default here too.
DEFAULT_RT_KIND = "offset"


def confusion_matrix(responses: Sequence[Response]) -> list[list[int]]:
    """Build the 5x5 confusion matrix ``matrix[true][responded]``.

    Rows and columns follow :data:`core.EMOTIONS_IN_ORDER`
    (Happy, Scared, Neutral, Sad, Angry). Unanswered trials are ignored.
    """
    pos = {emo: i for i, emo in enumerate(EMOTIONS_IN_ORDER)}
    matrix = [[0] * 5 for _ in range(5)]
    for r in responses:
        if r.responded is None:
            continue
        matrix[pos[r.true_emotion]][pos[r.responded]] += 1
    return matrix


@dataclass(frozen=True, slots=True)
class GroupStats:
    """Scores for one subset of trials (an emotion, a gender, or everything).

    ``mean_rt`` and ``pct_correct`` are ``None`` when the subset has no answered
    trials, rather than silently reporting 0 or NaN -- so an empty cell is
    unambiguous in a report.
    """

    n_presented: int          # trials in this subset (answered or not)
    n_answered: int           # trials with a response
    n_correct: int            # correct responses
    pct_correct: float | None  # 100 * n_correct / n_answered
    mean_rt: float | None      # mean reaction time (seconds), see rt_kind
    mean_replays: float | None  # mean number of replays per answered trial


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """Everything the reports need, computed once from the responses."""

    confusion: list[list[int]]
    emotion_order: tuple[Emotion, ...]
    per_emotion: dict[Emotion, GroupStats]
    per_gender: dict[Gender, GroupStats]
    total: GroupStats
    rt_kind: str


def _rt_value(response: Response, rt_kind: str) -> float | None:
    """Pick the onset- or offset-based RT off a response."""
    if rt_kind == "onset":
        return response.rt_onset
    if rt_kind == "offset":
        return response.rt_offset
    raise ValueError(f"rt_kind must be 'onset' or 'offset', got {rt_kind!r}")


def _mean(values: Sequence[float]) -> float | None:
    """Mean of a sequence, or ``None`` if it's empty."""
    return sum(values) / len(values) if values else None


def _group_stats(responses: Sequence[Response], rt_kind: str) -> GroupStats:
    """Compute the stats block for an arbitrary subset of responses."""
    answered = [r for r in responses if r.answered]
    n_correct = sum(1 for r in answered if r.is_correct)
    rts = [
        rt for r in answered if (rt := _rt_value(r, rt_kind)) is not None
    ]
    pct = 100.0 * n_correct / len(answered) if answered else None
    return GroupStats(
        n_presented=len(responses),
        n_answered=len(answered),
        n_correct=n_correct,
        pct_correct=pct,
        mean_rt=_mean(rts),
        mean_replays=_mean([r.n_replays for r in answered]),
    )


def summarize(
    responses: Sequence[Response],
    *,
    rt_kind: str = DEFAULT_RT_KIND,
) -> SessionSummary:
    """Compute the full session summary from a list of responses.

    Args:
        responses: The completed trials.
        rt_kind: Which reaction time to average -- ``"offset"`` (default) or
            ``"onset"``.

    Returns:
        A :class:`SessionSummary` with the confusion matrix plus per-emotion,
        per-gender, and total :class:`GroupStats`.
    """
    per_emotion = {
        emo: _group_stats([r for r in responses if r.true_emotion is emo], rt_kind)
        for emo in EMOTIONS_IN_ORDER
    }
    per_gender = {
        g: _group_stats([r for r in responses if r.gender is g], rt_kind)
        for g in Gender
    }
    return SessionSummary(
        confusion=confusion_matrix(responses),
        emotion_order=EMOTIONS_IN_ORDER,
        per_emotion=per_emotion,
        per_gender=per_gender,
        total=_group_stats(responses, rt_kind),
        rt_kind=rt_kind,
    )
