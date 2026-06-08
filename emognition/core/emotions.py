# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Emotion definitions for Emognition.

This module is the single source of truth for the five emotions the task tests,
and -- importantly -- for their *numeric ordering*. That ordering is not arbitrary:
it must match the original MATLAB program so that exported reports line up with a
decade of previously collected data.

    Homage to the original (savestate.m):
        writecell({'1: Happy';'2: Scared'; '3: Neutral'; '4: Sad'; '5: Angry'}, ...)

So the canonical index map, preserved here for backward compatibility, is:

    1 = Happy   2 = Scared   3 = Neutral   4 = Sad   5 = Angry

The 3-letter tags (ang/hap/sad/neu/sca) come from the audio-file naming convention
documented in Emognition2.m:

    "...the filename of the .wav audio inputs must ALWAYS end with ..._EMO_G.wav
     where EMO is a 3-letter tag for one of the 5 different emotions ...
     EMO tag can only be any of these five: 'ANG','HAP','SAD','NEU','SCA'."
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Emotion(IntEnum):
    """The five emotions, numbered to match the legacy MATLAB report layout.

    Using IntEnum (rather than a plain Enum) means ``int(Emotion.HAPPY) == 1``,
    which keeps the confusion-matrix / pressed-keys exports identical to the
    original program's column ordering.
    """

    HAPPY = 1
    SCARED = 2
    NEUTRAL = 3
    SAD = 4
    ANGRY = 5

    @property
    def tag(self) -> str:
        """The lowercase 3-letter tag used in audio filenames (e.g. 'hap')."""
        return _TAGS[self]

    @property
    def label(self) -> str:
        """Human-readable, title-cased label (e.g. 'Happy')."""
        return self.name.title()


# Three-letter filename tags. These are matched case-insensitively when parsing
# audio filenames (the original accepted 'ang', 'HaP', etc. all the same).
_TAGS: dict[Emotion, str] = {
    Emotion.ANGRY: "ang",
    Emotion.HAPPY: "hap",
    Emotion.SAD: "sad",
    Emotion.NEUTRAL: "neu",
    Emotion.SCARED: "sca",
}

# Reverse lookup: tag -> Emotion. Keys are lowercase; callers should .lower() first.
TAG_TO_EMOTION: dict[str, Emotion] = {tag: emo for emo, tag in _TAGS.items()}

# Convenience: the emotions in their canonical 1..5 order.
EMOTIONS_IN_ORDER: tuple[Emotion, ...] = tuple(sorted(Emotion, key=int))


class Sex(IntEnum):
    """Speaker sex, encoded by the trailing letter in the filename.

    'f' -> Female, 'm' -> Male, 'u' -> Unknown (for recordings whose speaker sex
    isn't recorded as female/male). Reports break accuracy down by speaker sex.
    """

    FEMALE = 0
    MALE = 1
    UNKNOWN = 2

    @property
    def tag(self) -> str:
        return {Sex.FEMALE: "f", Sex.MALE: "m", Sex.UNKNOWN: "u"}[self]

    @property
    def label(self) -> str:
        return self.name.title()  # "Female" / "Male" / "Unknown"


# Reverse lookup: filename tag -> Sex (lowercase keys).
TAG_TO_SEX: dict[str, Sex] = {s.tag: s for s in Sex}

# The sexes in enum order, for stable report rows.
SEXES_IN_ORDER: tuple[Sex, ...] = tuple(Sex)


@dataclass(frozen=True, slots=True)
class Stimulus:
    """One audio stimulus: its file path plus the truth it encodes.

    ``emotion`` is the correct answer for this clip; ``sex`` is the speaker's sex;
    ``recording_id`` is the free-form prefix of the filename (everything before
    the ``_EMO_SEX.wav`` ending) -- e.g. a speaker/take label, kept so individual
    recordings can be identified and filtered in the reports.
    """

    path: str
    emotion: Emotion
    sex: Sex
    recording_id: str = ""

    @property
    def filename(self) -> str:
        import os

        return os.path.basename(self.path)
