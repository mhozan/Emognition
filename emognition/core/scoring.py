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
  broken down per emotion, per speaker sex, and overall (the legacy
  "Percentages" sheet), plus the RT median / SD / IQR; and
* **bias-corrected agreement** -- Wagner's unbiased hit rate per emotion and
  Cohen's kappa overall. Raw percent-correct rewards a participant who answers
  "Neutral" to everything with 100 % for Neutral; these measures don't, which
  is why emotion-recognition papers report them.

Percent-correct for an emotion is ``100 * diagonal / row-sum`` -- correct
responses divided by the number of *answered* trials of that emotion, exactly as
the original computed ``tabl(i,i)/sum(tabl(i,:))`` (its table only ever held
answered trials). Today every recorded trial is answered, so this equals
correct / presented; if a response timeout is ever added, unanswered trials
are shown separately (``n_presented`` vs ``n_answered``) rather than counted
as errors.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field

from .emotions import Emotion, EMOTIONS_IN_ORDER, SEXES_IN_ORDER, Sex
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
    """Scores for one subset of trials (an emotion, a sex, or everything).

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
    n_rt: int = 0              # RTs behind mean_rt (answered minus RT-excluded trials)
    median_rt: float | None = None
    sd_rt: float | None = None   # sample SD (n - 1); None with fewer than 2 RTs
    iqr_rt: float | None = None  # Q3 - Q1 ("inclusive" quartiles); None with < 2 RTs


@dataclass(frozen=True, slots=True)
class SessionSummary:
    """Everything the reports need, computed once from the responses."""

    confusion: list[list[int]]
    emotion_order: tuple[Emotion, ...]
    per_emotion: dict[Emotion, GroupStats]
    per_sex: dict[Sex, GroupStats]
    total: GroupStats
    rt_kind: str
    # Wagner's unbiased hit rate per emotion (None: never presented or chosen).
    unbiased_hit_rate: dict[Emotion, float | None] = field(default_factory=dict)
    kappa: float | None = None                       # Cohen's kappa, all trials
    confusion_pct: list[list[float | None]] = field(default_factory=list)  # % of each row


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
    two = len(rts) >= 2
    q1, _q2, q3 = statistics.quantiles(rts, n=4, method="inclusive") if two else (None, None, None)
    return GroupStats(
        n_presented=len(responses),
        n_answered=len(answered),
        n_correct=n_correct,
        pct_correct=pct,
        mean_rt=_mean(rts),
        mean_replays=_mean([r.n_replays for r in answered]),
        n_rt=len(rts),
        median_rt=statistics.median(rts) if rts else None,
        sd_rt=statistics.stdev(rts) if two else None,
        iqr_rt=(q3 - q1) if two else None,
    )


def row_percentages(matrix: Sequence[Sequence[int]]) -> list[list[float | None]]:
    """Each confusion cell as % of its row (how often each answer was given per emotion).

    Rows with no presentations are all ``None``.
    """
    out: list[list[float | None]] = []
    for row in matrix:
        total = sum(row)
        out.append([100.0 * n / total if total else None for n in row])
    return out


def unbiased_hit_rates(matrix: Sequence[Sequence[int]]) -> list[float | None]:
    """Wagner's (1993) unbiased hit rate for each emotion, from the confusion matrix.

    ``Hu_i = A_ii^2 / (row_i * col_i)`` -- the hit rate (correct / times played)
    times the precision (correct / times chosen). Answering one emotion to
    everything gets that emotion a hit rate of 1 but an Hu of only its share of
    the trials. ``None`` when the emotion was never played or never chosen.

    Wagner, H. L. (1993). On measuring performance in category judgment studies
    of nonverbal behavior. *Journal of Nonverbal Behavior*, 17(1), 3-28.
    """
    cols = [sum(col) for col in zip(*matrix)] if matrix else []
    rates: list[float | None] = []
    for i, row in enumerate(matrix):
        hits, played, chosen = row[i], sum(row), cols[i]
        rates.append(hits * hits / (played * chosen) if played and chosen else None)
    return rates


def cohen_kappa(matrix: Sequence[Sequence[int]]) -> float | None:
    """Cohen's kappa: agreement with the true emotion beyond what chance predicts.

    ``kappa = (p_o - p_e) / (1 - p_e)`` with ``p_o`` the observed accuracy and
    ``p_e`` the agreement expected from the row and column totals. 1 is perfect,
    0 is chance level. ``None`` if there are no answered trials, or if chance
    agreement is already 1 (a single emotion played and chosen throughout).
    """
    n = sum(sum(row) for row in matrix)
    if n == 0:
        return None
    observed = sum(matrix[i][i] for i in range(len(matrix))) / n
    cols = [sum(col) for col in zip(*matrix)]
    expected = sum(sum(row) * cols[i] for i, row in enumerate(matrix)) / (n * n)
    if expected >= 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


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
        per-sex, and total :class:`GroupStats`.
    """
    per_emotion = {
        emo: _group_stats([r for r in responses if r.true_emotion is emo], rt_kind)
        for emo in EMOTIONS_IN_ORDER
    }
    per_sex = {
        s: _group_stats([r for r in responses if r.sex is s], rt_kind)
        for s in SEXES_IN_ORDER
    }
    confusion = confusion_matrix(responses)
    return SessionSummary(
        confusion=confusion,
        emotion_order=EMOTIONS_IN_ORDER,
        per_emotion=per_emotion,
        per_sex=per_sex,
        total=_group_stats(responses, rt_kind),
        rt_kind=rt_kind,
        unbiased_hit_rate=dict(zip(EMOTIONS_IN_ORDER, unbiased_hit_rates(confusion))),
        kappa=cohen_kappa(confusion),
        confusion_pct=row_percentages(confusion),
    )
