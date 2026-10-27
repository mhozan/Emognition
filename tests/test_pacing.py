# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Between-trial pacing (emognition/core/pacing.py): stars, breaks, the Next button."""

import pytest

from emognition.core.pacing import BREAK, NEXT, STAR, between_trials, star_slots, stars_earned


@pytest.mark.parametrize("done, expected", [
    (1, (NEXT,)),
    (4, (STAR, NEXT)),            # a star every 4
    (6, (BREAK,)),                # a break every 6 replaces the Next button
    (12, (STAR, BREAK)),
    (24, (STAR,)),                # the last trial: the "All done!" star, nothing to wait for
])
def test_steps_after_each_trial(done, expected):
    assert between_trials(done, 24, stars_every=4, break_every=6, next_button=True) == expected


def test_everything_is_off_by_default():
    assert all(between_trials(done, 10) == () for done in range(1, 11))


def test_stars_fill_a_row_and_a_resumed_session_keeps_them():
    assert star_slots(24, 4) == 6 and star_slots(10, 4) == 2 and star_slots(10, 0) == 0
    assert stars_earned(9, 4) == 2 and stars_earned(9, 0) == 0
