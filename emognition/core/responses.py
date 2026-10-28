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

from .emotions import Emotion, Sex, Stimulus


@dataclass(slots=True)
class Response:
    """One completed trial.

    Attributes:
        stimulus: The clip that was played (carries the true emotion + sex).
        responded: The emotion the participant chose, or ``None`` if they made no
            response (e.g. the trial was aborted).
        rt_onset: Reaction time in seconds measured from audio *onset*.
        rt_offset: Reaction time in seconds measured from audio *offset* (the
            default reported RT; mirrors the legacy ``reactiontime.m``). May be
            negative if the participant answered before the clip finished.
        n_replays: How many times the participant replayed the clip before
            answering (0 when replays are disabled or unused).
        background: The background picture on screen during the trial (its
            friendly name; "" for a plain window) -- lets an analysis check
            whether pictures affected performance.
        n_pauses: How many times the experimenter paused (P) or nearly quit (Esc,
            then "keep going") during this trial. Each time, the trial was
            replayed from the start, so the RT is valid, but the participant
            heard the clip more than once -- worth knowing in an analysis.
        rt_speech_offset: Reaction time from the end of *speech* -- the last
            moment within 40 dB of the clip's peak (audio/endpoints.py) --
            rather than the end of the file, so trailing silence and
            calibration padding don't shift it. Filled in after the session.
        choices: Every answer, in order, when practice's "retry until
            correct" made the participant try again (wrong faces are greyed
            out until the right one is chosen); empty when the first answer
            stood. Only the first -- :attr:`responded` -- is scored and timed;
            the rest show how the participant homed in on the right face.
    """

    stimulus: Stimulus
    responded: Emotion | None = None
    rt_onset: float | None = None
    rt_offset: float | None = None
    n_replays: int = 0
    background: str = ""
    n_pauses: int = 0
    choices: tuple[Emotion, ...] = ()
    rt_speech_offset: float | None = None

    @property
    def n_attempts(self) -> int:
        """Answers given on this trial: 1 normally, more after retries, 0 if unanswered."""
        return len(self.choices) if self.choices else int(self.responded is not None)

    @property
    def true_emotion(self) -> Emotion:
        """The correct answer for this trial."""
        return self.stimulus.emotion

    @property
    def sex(self) -> Sex:
        """The speaker's sex for this trial."""
        return self.stimulus.sex

    @property
    def answered(self) -> bool:
        """Whether the participant actually responded."""
        return self.responded is not None

    @property
    def is_correct(self) -> bool:
        """True iff the participant answered and the answer matches the clip."""
        return self.responded is not None and self.responded == self.true_emotion
