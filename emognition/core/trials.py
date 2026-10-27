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

Two additions the original didn't have: a shuffle that never puts more than N
clips of one emotion in a row (long runs invite response strategies like "it's
been sad four times, so...") and a small practice set picked from the clips.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .emotions import Emotion, EMOTIONS_IN_ORDER, SEXES_IN_ORDER, Sex, Stimulus


def build_trial_list(
    stimuli: Iterable[Stimulus],
    *,
    emotions: Iterable[Emotion] | None = None,
    shuffle: bool = True,
    rng: random.Random | None = None,
    max_run: int = 0,
) -> list[Stimulus]:
    """Return the clips to present, filtered to the tested emotions and ordered.

    Args:
        stimuli: All discovered stimuli (e.g. from :func:`core.scan_audio_dir`).
        emotions: The subset of emotions to test. ``None`` means all five.
        shuffle: If True, randomise presentation order (the default; the original
            offered a "Shuffle images randomly" option and shuffled audio order).
        rng: A seeded :class:`random.Random` for reproducible shuffles. If omitted
            a fresh, unseeded one is used.
        max_run: With *shuffle*, never more than this many clips of the same
            emotion in a row (0 = no limit: a plain shuffle, so existing seeds
            keep giving the same orders).

    Returns:
        A new list of :class:`Stimulus` in presentation order. Input is not
        mutated.

    Raises:
        ValueError: if the clips can't be ordered within *max_run* (say, most
            of them are one emotion).
    """
    wanted = set(EMOTIONS_IN_ORDER if emotions is None else emotions)
    ordered = [s for s in stimuli if s.emotion in wanted]
    if shuffle:
        rng = rng or random.Random()
        if max_run > 0:
            return _shuffle_with_max_run(ordered, max_run, rng)
        rng.shuffle(ordered)
    return ordered


def _can_finish(counts: dict[Emotion, int], last: Emotion | None, run: int, max_run: int) -> bool:
    """Can clips with these *counts* still follow, given the current run of *last*?

    An emotion with ``n`` clips needs other clips to break it into runs of at
    most *max_run*: with ``others`` other clips there are ``others + 1`` gaps to
    fill, except that the gap right now already holds *run* clips of *last*.
    That bound, checked for every emotion, is both necessary and sufficient.
    """
    total = sum(counts.values())
    for emotion, n in counts.items():
        room = max_run * (total - n) + (max_run - run if emotion == last else max_run)
        if n > room:
            return False
    return True


def _shuffle_with_max_run(clips: list[Stimulus], max_run: int, rng: random.Random) -> list[Stimulus]:
    """A random order with no more than *max_run* of one emotion in a row.

    Each step picks uniformly among the clips that keep the rest arrangeable
    (:func:`_can_finish`), so it never paints itself into a corner -- unlike
    reshuffling until an order happens to pass, which for "no two in a row"
    over 120 clips would essentially never succeed.
    """
    counts: dict[Emotion, int] = {}
    for clip in clips:
        counts[clip.emotion] = counts.get(clip.emotion, 0) + 1
    if not _can_finish(counts, None, 0, max_run):
        raise ValueError(
            f"these clips can't be ordered with at most {max_run} of one emotion in a row "
            "(too many of one emotion); raise the limit or test more emotions"
        )
    pool = list(clips)
    rng.shuffle(pool)
    order: list[Stimulus] = []
    last, run = None, 0
    while pool:
        allowed = set()
        for emotion in {c.emotion for c in pool}:
            next_run = run + 1 if emotion == last else 1
            if next_run > max_run:
                continue
            counts[emotion] -= 1
            if _can_finish(counts, emotion, next_run, max_run):
                allowed.add(emotion)
            counts[emotion] += 1
        pick = rng.choice([i for i, c in enumerate(pool) if c.emotion in allowed])
        clip = pool.pop(pick)
        counts[clip.emotion] -= 1
        run = run + 1 if clip.emotion == last else 1
        last = clip.emotion
        order.append(clip)
    return order


def pick_practice(
    stimuli: Iterable[Stimulus],
    n: int,
    *,
    emotions: Iterable[Emotion] | None = None,
    rng: random.Random | None = None,
) -> list[Stimulus]:
    """*n* practice clips of the tested emotions, as varied as possible.

    Takes one clip of each emotion (in random order) before any emotion gets a
    second, so even a 3-trial practice shows three different emotions.
    """
    rng = rng or random.Random()
    wanted = set(EMOTIONS_IN_ORDER if emotions is None else emotions)
    by_emotion: dict[Emotion, list[Stimulus]] = {}
    for clip in stimuli:
        if clip.emotion in wanted:
            by_emotion.setdefault(clip.emotion, []).append(clip)
    for group in by_emotion.values():
        rng.shuffle(group)
    picked: list[Stimulus] = []
    while len(picked) < n and any(by_emotion.values()):
        round_ = [e for e in by_emotion if by_emotion[e]]
        rng.shuffle(round_)
        for emotion in round_:
            if len(picked) == n:
                break
            picked.append(by_emotion[emotion].pop())
    return picked


@dataclass(frozen=True, slots=True)
class StimulusBreakdown:
    """How many clips of each kind are in a set (for the pre-run confirmation).

    Mirrors the counts the original ``analyzeaudiodir.m`` showed the experimenter
    before starting ("Valid wav files / Female / Male / per-emotion f,m").
    """

    total: int
    by_sex: dict[Sex, int]
    by_emotion: dict[Emotion, int]
    by_emotion_sex: dict[tuple[Emotion, Sex], int]


def summarize_stimuli(stimuli: Sequence[Stimulus]) -> StimulusBreakdown:
    """Count a stimulus set by sex, emotion, and emotion×sex."""
    by_sex: dict[Sex, int] = {s: 0 for s in SEXES_IN_ORDER}
    by_emotion: dict[Emotion, int] = {e: 0 for e in EMOTIONS_IN_ORDER}
    by_emotion_sex: dict[tuple[Emotion, Sex], int] = {
        (e, s): 0 for e in EMOTIONS_IN_ORDER for s in SEXES_IN_ORDER
    }
    for stim in stimuli:
        by_sex[stim.sex] += 1
        by_emotion[stim.emotion] += 1
        by_emotion_sex[(stim.emotion, stim.sex)] += 1
    return StimulusBreakdown(
        total=len(stimuli),
        by_sex=by_sex,
        by_emotion=by_emotion,
        by_emotion_sex=by_emotion_sex,
    )
