# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""What happens between two trials: the optional pacing.

All of it is off by default, and none of it depends on how well the participant is
doing -- it marks *progress*, so it can't bias which answers they give:

* a **star** every N trials (a row under the progress bar fills up; the last
  one, if the session ends on it, says "All done!");
* a **break** screen every N trials, which waits for a click on "Continue";
* a **Next** button after every other trial -- the original's "Extra button"
  ("After a response to each audio, the program waits for an extra click on a
  button in the middle of the screen before playing the next audio").

Nothing between trials is timed: the trial just finished is already saved.
"""

from __future__ import annotations

STAR = "star"
BREAK = "break"
NEXT = "next"


def between_trials(
    done: int,
    total: int,
    *,
    stars_every: int = 0,
    break_every: int = 0,
    next_button: bool = False,
) -> tuple[str, ...]:
    """The steps to show after trial *done* (1-based) of *total*, in order.

    A star can come after the last trial (the "All done!" one); a break or the
    Next button never does -- there's nothing left to wait for. A break replaces
    the Next button (it waits for a click already).

    >>> between_trials(5, 20, stars_every=5, break_every=10, next_button=True)
    ('star', 'next')
    >>> between_trials(10, 20, stars_every=5, break_every=10, next_button=True)
    ('star', 'break')
    >>> between_trials(20, 20, stars_every=5, break_every=10, next_button=True)
    ('star',)
    """
    steps: list[str] = []
    if stars_every > 0 and done % stars_every == 0:
        steps.append(STAR)
    if done < total:
        if break_every > 0 and done % break_every == 0:
            steps.append(BREAK)
        elif next_button:
            steps.append(NEXT)
    return tuple(steps)


def star_slots(total: int, stars_every: int) -> int:
    """How many stars a session of *total* trials can earn (0 when stars are off)."""
    return total // stars_every if stars_every > 0 else 0


def stars_earned(done: int, stars_every: int) -> int:
    """Stars earned once *done* trials are finished (a resumed session starts here)."""
    return done // stars_every if stars_every > 0 else 0
