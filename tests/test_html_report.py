# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the HTML report (assert on the rendered markup string)."""

from emognition.core import Emotion, Sex, Response, Stimulus
from emognition.reports import SessionInfo, render_html_report


def _resp(true, gender, responded, rt_offset=None, n_replays=0, fname="x_hap_f.wav"):
    stim = Stimulus(path=fname, emotion=true, sex=gender)
    rt_onset = None if rt_offset is None else rt_offset + 1.0
    return Response(stim, responded, rt_onset, rt_offset, n_replays)


def _responses():
    return [
        _resp(Emotion.HAPPY, Sex.FEMALE, Emotion.HAPPY, 0.5, 0, "01_hap_f.wav"),
        _resp(Emotion.HAPPY, Sex.MALE, Emotion.SAD, 1.0, 1, "02_hap_m.wav"),
        _resp(Emotion.SAD, Sex.FEMALE, Emotion.SAD, 0.7, 0, "03_sad_f.wav"),
        _resp(Emotion.ANGRY, Sex.MALE, None, None, 0, "04_ang_m.wav"),
    ]


def test_is_self_contained_html_document():
    html = render_html_report(_responses())
    assert html.lstrip().startswith("<!doctype html>")
    assert "<style>" in html          # CSS is inline, not linked
    assert "http://" not in html and "https://" not in html  # no external assets
    assert html.rstrip().endswith("</html>")


def test_contains_key_numbers():
    html = render_html_report(_responses(), info=SessionInfo(participant="P01"))
    assert "Confusion matrix" in html
    assert "P01" in html
    assert "66.7" in html             # total accuracy 2/3 -> 66.7%
    assert "04_ang_m.wav" in html     # per-trial detail present


def test_escapes_user_input():
    # A participant id containing HTML must be escaped, not injected.
    html = render_html_report(
        _responses(), info=SessionInfo(participant="<script>x</script>")
    )
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
