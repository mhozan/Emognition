# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for reaction-time quality flagging and RT scrubbing."""

import pytest

from emognition.core import (
    Emotion,
    Sex,
    Response,
    RtFlag,
    Stimulus,
    flag_responses,
    scrub_flagged_rts,
    summarize,
)


def _resp(rt_onset, responded=Emotion.HAPPY):
    stim = Stimulus(path="x_hap_f.wav", emotion=Emotion.HAPPY, sex=Sex.FEMALE)
    rt_offset = None if rt_onset is None else rt_onset - 1.8
    return Response(stim, responded, rt_onset, rt_offset, 0)


def test_no_response_flag():
    flags = flag_responses([_resp(None, responded=None)])
    assert flags == [RtFlag.NO_RESPONSE]


def test_anticipatory_flag():
    # 100 ms after onset -> too fast to be a real decision
    flags = flag_responses([_resp(0.10), _resp(0.80)])
    assert flags[0] is RtFlag.ANTICIPATORY
    assert flags[1] is RtFlag.OK


def test_slow_outlier_flag():
    # a tight cluster plus one extreme slow response
    cluster = [_resp(rt) for rt in (2.0, 2.1, 1.9, 2.05, 2.0, 1.95)]
    slow = _resp(20.0)
    flags = flag_responses(cluster + [slow], rt_kind="onset")
    assert flags[-1] is RtFlag.SLOW_OUTLIER
    assert all(f is RtFlag.OK for f in flags[:-1])


def test_scrub_excludes_flagged_rts_from_means_but_not_accuracy():
    responses = [_resp(0.10), _resp(2.0), _resp(2.2)]  # first is anticipatory
    flags = flag_responses(responses)

    scrubbed = scrub_flagged_rts(responses, flags)
    # The anticipatory trial keeps its (correct) response...
    assert scrubbed[0].responded is Emotion.HAPPY
    assert scrubbed[0].is_correct
    # ...but its RT is nulled so it won't enter the means.
    assert scrubbed[0].rt_onset is None

    full = summarize(responses, rt_kind="onset")
    clean = summarize(scrubbed, rt_kind="onset")
    # Accuracy identical (all 3 correct, counted either way).
    assert full.total.pct_correct == clean.total.pct_correct == 100.0
    # Mean RT differs: clean excludes the 0.10 s anticipatory trial.
    assert clean.total.mean_rt == pytest.approx(2.1)   # mean(2.0, 2.2)
    assert full.total.mean_rt == pytest.approx((0.10 + 2.0 + 2.2) / 3)


def test_too_few_points_skips_outlier_detection():
    # With only one eligible RT, no spread can be estimated -> no outlier flag.
    flags = flag_responses([_resp(99.0)])
    assert flags == [RtFlag.OK]


def test_outliers_are_still_caught_when_most_rts_tie():
    # Frame-quantised RTs often tie; with >=50% identical values the MAD is 0,
    # which used to switch slow-outlier detection off entirely.
    from emognition.core.quality import MIN_ROBUST_SD_S

    onsets = [2.3] * 9 + [31.8]                      # offsets: nine 0.5 s and one 30 s
    flags = flag_responses([_resp(t) for t in onsets])
    assert flags[-1] is RtFlag.SLOW_OUTLIER
    assert all(f is RtFlag.OK for f in flags[:-1])
    near = [2.3] * 9 + [2.3 + 2 * MIN_ROBUST_SD_S]   # within the floor's tolerance
    assert flag_responses([_resp(t) for t in near])[-1] is RtFlag.OK
