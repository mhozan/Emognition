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
    Gender,
    Response,
    Stimulus,
    confusion_matrix,
    summarize,
)

# Index of each emotion in the canonical confusion-matrix order.
H, SC, NE, SA, AN = 0, 1, 2, 3, 4


def _resp(true, gender, responded, rt_offset=None, n_replays=0):
    stim = Stimulus(path="x.wav", emotion=true, gender=gender)
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
    _resp(Emotion.HAPPY, Gender.FEMALE, Emotion.HAPPY, 0.5, 0),
    _resp(Emotion.HAPPY, Gender.MALE, Emotion.SAD, 1.0, 1),
    _resp(Emotion.SAD, Gender.FEMALE, Emotion.SAD, 0.7, 0),
    _resp(Emotion.ANGRY, Gender.MALE, None),
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


def test_per_gender_stats():
    s = summarize(RESPONSES)
    fem = s.per_gender[Gender.FEMALE]
    assert fem.n_answered == 2 and fem.n_correct == 2
    assert fem.pct_correct == pytest.approx(100.0)
    assert fem.mean_rt == pytest.approx(0.6)  # mean(0.5, 0.7)

    male = s.per_gender[Gender.MALE]
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
