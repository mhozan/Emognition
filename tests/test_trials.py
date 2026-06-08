# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for trial-list building and stimulus breakdown."""

import random

from emognition.core import (
    Emotion,
    Gender,
    Stimulus,
    build_trial_list,
    summarize_stimuli,
)


def _stim(emotion: Emotion, gender: Gender, n: int = 0) -> Stimulus:
    return Stimulus(path=f"{emotion.tag}_{gender.tag}_{n}.wav", emotion=emotion, gender=gender)


def _full_set() -> list[Stimulus]:
    # one clip per emotion x gender = 10 stimuli
    return [_stim(e, g) for e in Emotion for g in Gender]


def test_no_shuffle_preserves_order_and_does_not_mutate_input():
    stimuli = _full_set()
    snapshot = list(stimuli)
    result = build_trial_list(stimuli, shuffle=False)
    assert result == snapshot          # same order
    assert stimuli == snapshot         # input untouched
    assert result is not stimuli       # new list


def test_emotion_subset_filters():
    stimuli = _full_set()
    result = build_trial_list(stimuli, emotions=[Emotion.HAPPY, Emotion.SAD], shuffle=False)
    assert {s.emotion for s in result} == {Emotion.HAPPY, Emotion.SAD}
    assert len(result) == 4  # 2 emotions x 2 genders


def test_seeded_shuffle_is_reproducible():
    stimuli = _full_set()
    a = build_trial_list(stimuli, shuffle=True, rng=random.Random(42))
    b = build_trial_list(stimuli, shuffle=True, rng=random.Random(42))
    assert a == b                       # same seed -> same order
    assert len(a) == len(stimuli)       # shuffle keeps every item


def test_summarize_stimuli_counts():
    stimuli = _full_set()
    bd = summarize_stimuli(stimuli)
    assert bd.total == 10
    assert bd.by_gender[Gender.FEMALE] == 5
    assert bd.by_gender[Gender.MALE] == 5
    assert all(bd.by_emotion[e] == 2 for e in Emotion)
    assert bd.by_emotion_gender[(Emotion.ANGRY, Gender.MALE)] == 1
