# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Reaction-time arithmetic.

The original ``reactiontime.m`` reconstructed reaction times *after the fact*
from a stream of tagged timestamps (-1001 click, -1002 stop, -1009 replay, -9999
pause, -9998 resume). That post-hoc bookkeeping existed because the MATLAB GUI
couldn't cleanly hand the timing back at the moment of the click.

With PsychoPy we capture timestamps directly at the moment of the response, so
the maths collapses to something simple and obviously correct. We report RT two
ways (the user wants both; **offset is the default**, matching the legacy tool,
which measured from the audio "stop" instant to the click):

    rt_onset  = press_time - onset_time
    rt_offset = rt_onset - clip_duration            # == press_time - offset_time

When replays are allowed, RT is measured from the **most recent** playback's
onset -- exactly the intent of the original's "reaction since the latest play".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReactionTime:
    """A reaction time expressed both ways, in seconds."""

    from_onset: float
    from_offset: float


def reaction_time(
    press_time: float,
    onset_time: float,
    clip_duration: float,
) -> ReactionTime:
    """Compute onset- and offset-relative reaction times.

    Args:
        press_time: Timestamp of the participant's response (same clock as
            ``onset_time``).
        onset_time: Timestamp of the (most recent) audio onset. If the clip was
            replayed, pass the latest replay's onset so RT is measured from it.
        clip_duration: Length of the clip in seconds.

    Returns:
        A :class:`ReactionTime`. ``from_offset`` may be negative if the response
        came before the clip finished.
    """
    rt_onset = press_time - onset_time
    return ReactionTime(from_onset=rt_onset, from_offset=rt_onset - clip_duration)
