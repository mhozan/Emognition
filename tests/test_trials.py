# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for trial-list building and stimulus breakdown."""

import random

import pytest

from emognition.core import (
    EMOTIONS_IN_ORDER,
    Emotion,
    Sex,
    Stimulus,
    build_trial_list,
    summarize_stimuli,
)


def _stim(emotion: Emotion, gender: Sex, n: int = 0) -> Stimulus:
    return Stimulus(path=f"{emotion.tag}_{gender.tag}_{n}.wav", emotion=emotion, sex=gender)


def _full_set() -> list[Stimulus]:
    # one clip per emotion x sex (female/male) = 10 stimuli
    return [_stim(e, g) for e in Emotion for g in (Sex.FEMALE, Sex.MALE)]


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
    assert bd.by_sex[Sex.FEMALE] == 5
    assert bd.by_sex[Sex.MALE] == 5
    assert all(bd.by_emotion[e] == 2 for e in Emotion)
    assert bd.by_emotion_sex[(Emotion.ANGRY, Sex.MALE)] == 1


# --- run-limited shuffle (Phase 5) ---------------------------------

def _longest_run(order) -> int:
    import itertools

    return max(len(list(group)) for _, group in itertools.groupby(s.emotion for s in order))


def _big_set() -> list[Stimulus]:
    return [_stim(e, Sex.FEMALE, n) for e in EMOTIONS_IN_ORDER for n in range(24)]   # 120 clips


@pytest.mark.parametrize("max_run", [1, 2, 3])
def test_max_run_is_never_exceeded_and_every_clip_stays(max_run):
    clips = _big_set()
    for seed in range(50):
        order = build_trial_list(clips, rng=random.Random(seed), max_run=max_run)
        assert _longest_run(order) <= max_run
        assert sorted(s.path for s in order) == sorted(s.path for s in clips)


def test_max_run_orders_are_reproducible_and_off_means_a_plain_shuffle():
    clips = _big_set()
    assert build_trial_list(clips, rng=random.Random(4), max_run=2) == \
        build_trial_list(clips, rng=random.Random(4), max_run=2)
    plain = list(clips)
    random.Random(4).shuffle(plain)
    assert build_trial_list(clips, rng=random.Random(4)) == plain        # seeds keep their orders


def test_an_impossible_max_run_is_refused():
    lopsided = [_stim(Emotion.HAPPY, Sex.FEMALE, n) for n in range(5)] + [_stim(Emotion.SAD, Sex.MALE)]
    with pytest.raises(ValueError, match="in a row"):
        build_trial_list(lopsided, rng=random.Random(1), max_run=2)      # 5 happy, 1 separator
    assert _longest_run(build_trial_list(lopsided, rng=random.Random(1), max_run=3)) <= 3
