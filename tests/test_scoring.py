# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for confusion matrix + summary statistics (the report inputs)."""

import pytest

from emognition.core import (
    Emotion,
    Sex,
    Response,
    Stimulus,
    confusion_matrix,
    summarize,
)

# Index of each emotion in the canonical confusion-matrix order.
H, SC, NE, SA, AN = 0, 1, 2, 3, 4


def _resp(true, gender, responded, rt_offset=None, n_replays=0):
    stim = Stimulus(path="x.wav", emotion=true, sex=gender)
    rt_onset = None if rt_offset is None else rt_offset + 1.0  # onset = offset + duration(=1)
    return Response(
        stimulus=stim,
        responded=responded,
        rt_onset=rt_onset,
        rt_offset=rt_offset,
        n_replays=n_replays,
    )


# A small, hand-checkable scenario reused across tests:
#   1) Happy/F  -> Happy  (correct,   rt_off=0.5, 0 replays)
#   2) Happy/M  -> Sad    (incorrect, rt_off=1.0, 1 replay)
#   3) Sad/F    -> Sad    (correct,   rt_off=0.7, 0 replays)
#   4) Angry/M  -> (no response)
RESPONSES = [
    _resp(Emotion.HAPPY, Sex.FEMALE, Emotion.HAPPY, 0.5, 0),
    _resp(Emotion.HAPPY, Sex.MALE, Emotion.SAD, 1.0, 1),
    _resp(Emotion.SAD, Sex.FEMALE, Emotion.SAD, 0.7, 0),
    _resp(Emotion.ANGRY, Sex.MALE, None),
]


def test_confusion_matrix_rows_true_cols_responded():
    m = confusion_matrix(RESPONSES)
    assert m[H][H] == 1   # Happy answered Happy
    assert m[H][SA] == 1  # Happy answered Sad
    assert m[SA][SA] == 1  # Sad answered Sad
    # unanswered Angry trial contributes nothing
    assert sum(sum(row) for row in m) == 3


def test_per_emotion_stats():
    s = summarize(RESPONSES)  # default rt_kind="offset"
    hap = s.per_emotion[Emotion.HAPPY]
    assert (hap.n_presented, hap.n_answered, hap.n_correct) == (2, 2, 1)
    assert hap.pct_correct == pytest.approx(50.0)
    assert hap.mean_rt == pytest.approx(0.75)      # mean(0.5, 1.0)
    assert hap.mean_replays == pytest.approx(0.5)  # mean(0, 1)

    ang = s.per_emotion[Emotion.ANGRY]
    assert ang.n_presented == 1 and ang.n_answered == 0
    assert ang.pct_correct is None and ang.mean_rt is None  # no data -> None, not 0


def test_per_sex_stats():
    s = summarize(RESPONSES)
    fem = s.per_sex[Sex.FEMALE]
    assert fem.n_answered == 2 and fem.n_correct == 2
    assert fem.pct_correct == pytest.approx(100.0)
    assert fem.mean_rt == pytest.approx(0.6)  # mean(0.5, 0.7)

    male = s.per_sex[Sex.MALE]
    assert male.n_presented == 2 and male.n_answered == 1
    assert male.pct_correct == pytest.approx(0.0)
    assert male.mean_rt == pytest.approx(1.0)


def test_total_stats():
    s = summarize(RESPONSES)
    assert s.total.n_presented == 4
    assert s.total.n_answered == 3
    assert s.total.n_correct == 2
    assert s.total.pct_correct == pytest.approx(200.0 / 3)
    assert s.total.mean_rt == pytest.approx((0.5 + 1.0 + 0.7) / 3)


def test_rt_kind_onset_uses_onset_values():
    s = summarize(RESPONSES, rt_kind="onset")
    # onset = offset + 1.0 in our fixture, so Happy mean = mean(1.5, 2.0) = 1.75
    assert s.per_emotion[Emotion.HAPPY].mean_rt == pytest.approx(1.75)


def test_invalid_rt_kind_raises():
    with pytest.raises(ValueError):
        summarize(RESPONSES, rt_kind="banana")


# --- bias-corrected measures and RT spread (Phase 5) ------------------------------

def _matrix(cells):
    """5x5 confusion matrix from {(true_index, chosen_index): count}."""
    m = [[0] * 5 for _ in range(5)]
    for (i, j), n in cells.items():
        m[i][j] = n
    return m


def test_unbiased_hit_rate_and_kappa_by_hand():
    from emognition.core import cohen_kappa, row_percentages, unbiased_hit_rates

    HAP, SAD = 0, 3
    m = _matrix({(HAP, HAP): 3, (HAP, SAD): 1, (SAD, HAP): 2, (SAD, SAD): 2})
    hu = unbiased_hit_rates(m)
    assert hu[HAP] == pytest.approx(9 / (4 * 5))       # 3^2 / (played 4 * chosen 5)
    assert hu[SAD] == pytest.approx(4 / (4 * 3))
    assert hu[1] is None and hu[2] is None and hu[4] is None   # never played
    assert cohen_kappa(m) == pytest.approx(0.25)       # po 0.625, pe 0.5
    assert row_percentages(m)[HAP] == [75.0, 0.0, 0.0, 25.0, 0.0]
    assert row_percentages(m)[1] == [None] * 5


def test_answering_one_emotion_to_everything_is_exposed():
    from emognition.core import cohen_kappa, unbiased_hit_rates

    NEU = 2
    m = _matrix({(i, NEU): 2 for i in range(5)})       # "Neutral" every time
    assert unbiased_hit_rates(m)[NEU] == pytest.approx(0.2)   # % correct would say 100
    assert cohen_kappa(m) == pytest.approx(0.0)
    assert cohen_kappa(_matrix({})) is None
    assert cohen_kappa(_matrix({(0, 0): 4})) is None   # chance agreement is already 1


def test_rt_spread_median_sd_iqr():
    stim = Stimulus(path="x_hap_f.wav", emotion=Emotion.HAPPY, sex=Sex.FEMALE)
    rs = [Response(stim, Emotion.HAPPY, rt + 1.0, rt, 0) for rt in (0.5, 0.7, 0.9, 1.1)]
    t = summarize(rs).total
    assert t.median_rt == pytest.approx(0.8)
    assert t.sd_rt == pytest.approx(0.2582, abs=1e-4)  # sample SD (n - 1)
    assert t.iqr_rt == pytest.approx(0.3)              # inclusive quartiles 0.65 .. 0.95
    one = summarize(rs[:1]).total
    assert one.median_rt == pytest.approx(0.5) and one.sd_rt is None and one.iqr_rt is None


def test_attempts_count_retries_but_only_the_first_answer_is_scored():
    from emognition.core import Response, Stimulus

    stim = Stimulus("/c/a_sad_f.wav", Emotion.SAD, Sex.FEMALE)
    retried = Response(stim, Emotion.ANGRY, 1.5, 0.6, choices=(Emotion.ANGRY, Emotion.SAD))
    assert retried.n_attempts == 2 and not retried.is_correct       # scored on "Angry"
    assert Response(stim, Emotion.SAD, 1.5, 0.6).n_attempts == 1
    assert Response(stim).n_attempts == 0                             # unanswered
