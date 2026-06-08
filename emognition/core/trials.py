# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Building the trial sequence before an experiment starts.

This is the UI-free half of what the original ``preproceed.m`` did: take the
stimuli discovered in the audio folder, keep only the emotions being tested, and
put them in presentation order (optionally shuffled). Deterministic when given a
seeded RNG, which is what makes it testable and lets a session be reproduced.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .emotions import Emotion, EMOTIONS_IN_ORDER, Gender, Stimulus


def build_trial_list(
    stimuli: Iterable[Stimulus],
    *,
    emotions: Iterable[Emotion] | None = None,
    shuffle: bool = True,
    rng: random.Random | None = None,
) -> list[Stimulus]:
    """Return the clips to present, filtered to the tested emotions and ordered.

    Args:
        stimuli: All discovered stimuli (e.g. from :func:`core.scan_audio_dir`).
        emotions: The subset of emotions to test. ``None`` means all five.
        shuffle: If True, randomise presentation order (the default; the original
            offered a "Shuffle images randomly" option and shuffled audio order).
        rng: A seeded :class:`random.Random` for reproducible shuffles. If omitted
            a fresh, unseeded one is used.

    Returns:
        A new list of :class:`Stimulus` in presentation order. Input is not
        mutated.
    """
    wanted = set(EMOTIONS_IN_ORDER if emotions is None else emotions)
    ordered = [s for s in stimuli if s.emotion in wanted]
    if shuffle:
        (rng or random.Random()).shuffle(ordered)
    return ordered


@dataclass(frozen=True, slots=True)
class StimulusBreakdown:
    """How many clips of each kind are in a set (for the pre-run confirmation).

    Mirrors the counts the original ``analyzeaudiodir.m`` showed the experimenter
    before starting ("Valid wav files / Female / Male / per-emotion f,m").
    """

    total: int
    by_gender: dict[Gender, int]
    by_emotion: dict[Emotion, int]
    by_emotion_gender: dict[tuple[Emotion, Gender], int]


def summarize_stimuli(stimuli: Sequence[Stimulus]) -> StimulusBreakdown:
    """Count a stimulus set by gender, emotion, and emotion×gender."""
    by_gender: dict[Gender, int] = {g: 0 for g in Gender}
    by_emotion: dict[Emotion, int] = {e: 0 for e in EMOTIONS_IN_ORDER}
    by_emotion_gender: dict[tuple[Emotion, Gender], int] = {
        (e, g): 0 for e in EMOTIONS_IN_ORDER for g in Gender
    }
    for s in stimuli:
        by_gender[s.gender] += 1
        by_emotion[s.emotion] += 1
        by_emotion_gender[(s.emotion, s.gender)] += 1
    return StimulusBreakdown(
        total=len(stimuli),
        by_gender=by_gender,
        by_emotion=by_emotion,
        by_emotion_gender=by_emotion_gender,
    )
