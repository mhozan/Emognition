# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The record of what happened on a single trial.

A :class:`Response` is the atomic result of one presentation: which clip was
played (and therefore the correct answer), what the participant pressed, how long
they took (two ways), and how many times they replayed the clip. The experiment
window produces these; the scoring module consumes them. Keeping this a plain,
UI-free dataclass is what lets us unit-test all the scoring maths without a
display or audio device.
"""

from __future__ import annotations

from dataclasses import dataclass

from .emotions import Emotion, Gender, Stimulus


@dataclass(slots=True)
class Response:
    """One completed trial.

    Attributes:
        stimulus: The clip that was played (carries the true emotion + gender).
        responded: The emotion the participant chose, or ``None`` if they made no
            response (e.g. the trial was aborted).
        rt_onset: Reaction time in seconds measured from audio *onset*.
        rt_offset: Reaction time in seconds measured from audio *offset* (the
            default reported RT; mirrors the legacy ``reactiontime.m``). May be
            negative if the participant answered before the clip finished.
        n_replays: How many times the participant replayed the clip before
            answering (0 when replays are disabled or unused).
    """

    stimulus: Stimulus
    responded: Emotion | None = None
    rt_onset: float | None = None
    rt_offset: float | None = None
    n_replays: int = 0

    @property
    def true_emotion(self) -> Emotion:
        """The correct answer for this trial."""
        return self.stimulus.emotion

    @property
    def gender(self) -> Gender:
        """The speaker's gender for this trial."""
        return self.stimulus.gender

    @property
    def answered(self) -> bool:
        """Whether the participant actually responded."""
        return self.responded is not None

    @property
    def is_correct(self) -> bool:
        """True iff the participant answered and the answer matches the clip."""
        return self.responded is not None and self.responded == self.true_emotion
