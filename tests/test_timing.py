# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for reaction-time arithmetic."""

import pytest

from emognition.core import reaction_time


def test_onset_and_offset():
    # clip starts at t=10.0, lasts 2.0s (so it ends at 12.0); response at 12.5s
    rt = reaction_time(press_time=12.5, onset_time=10.0, clip_duration=2.0)
    assert rt.from_onset == pytest.approx(2.5)
    assert rt.from_offset == pytest.approx(0.5)


def test_offset_is_negative_when_answered_before_clip_ends():
    # responded at 11.0s, before the 2.0s clip (started at 10.0) finished at 12.0s
    rt = reaction_time(press_time=11.0, onset_time=10.0, clip_duration=2.0)
    assert rt.from_onset == pytest.approx(1.0)
    assert rt.from_offset == pytest.approx(-1.0)


def test_offset_equals_onset_minus_duration():
    rt = reaction_time(press_time=5.234, onset_time=1.0, clip_duration=1.777)
    assert rt.from_offset == pytest.approx(rt.from_onset - 1.777)
