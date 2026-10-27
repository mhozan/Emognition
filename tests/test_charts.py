# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the hand-built SVG reaction-time chart."""

import xml.dom.minidom as minidom

from emognition.core import Emotion, Sex, Response, Stimulus
from emognition.reports import reaction_time_svg


def _resp(responded, rt_offset, n_replays=0):
    stim = Stimulus(path="x_hap_f.wav", emotion=Emotion.HAPPY, sex=Sex.FEMALE)
    rt_onset = None if rt_offset is None else rt_offset + 1.8
    return Response(stim, responded, rt_onset, rt_offset, n_replays)


def test_returns_wellformed_svg():
    svg = reaction_time_svg([
        _resp(Emotion.HAPPY, 0.5),
        _resp(Emotion.SAD, 0.9, n_replays=2),
        _resp(Emotion.HAPPY, 1.3),
    ])
    assert svg.startswith("<svg")
    # Must be parseable XML (catches unescaped/broken markup).
    minidom.parseString(svg)
    assert "<circle" in svg and "<polyline" in svg


def test_marker_radius_grows_with_replays():
    # One trial with 0 replays vs one with 3; the latter circle must be larger.
    svg0 = reaction_time_svg([_resp(Emotion.HAPPY, 0.5, n_replays=0)])
    svg3 = reaction_time_svg([_resp(Emotion.HAPPY, 0.5, n_replays=3)])

    def first_radius(svg):
        doc = minidom.parseString(svg)
        return float(doc.getElementsByTagName("circle")[0].getAttribute("r"))

    assert first_radius(svg3) > first_radius(svg0)


def test_no_data_placeholder():
    # All unanswered -> no plottable points -> graceful placeholder.
    svg = reaction_time_svg([_resp(None, None)])
    assert "no reaction-time data" in svg
    minidom.parseString(svg)


# --- range, NaN and marker-size robustness (Phase 3) --------------------------

def _rt_responses(offsets, replays=0):
    from emognition.core import Emotion, Response, Sex, Stimulus

    stim = Stimulus(path="/c/x_hap_f.wav", emotion=Emotion.HAPPY, sex=Sex.FEMALE)
    return [Response(stimulus=stim, responded=Emotion.HAPPY, rt_onset=o + 1.0, rt_offset=o,
                     n_replays=replays) for o in offsets]


def _circles(svg):
    import re

    return [(float(cx), float(cy), float(r))
            for cx, cy, r in re.findall(r"<circle cx='([-\d.]+)' cy='([-\d.]+)' r='([\d.]+)'", svg)]


def test_negative_rts_stay_inside_the_plot():
    svg = reaction_time_svg(_rt_responses([-0.5, -0.2]))
    # plot area spans y = 16 (top) .. 260 - 36 = 224 (bottom)
    assert all(16 <= cy <= 224 for _, cy, _ in _circles(svg))
    single = reaction_time_svg(_rt_responses([-0.3]))
    assert all(16 <= cy <= 224 for _, cy, _ in _circles(single))


def test_nan_rts_are_skipped_not_drawn():
    svg = reaction_time_svg(_rt_responses([0.4, float("nan"), 0.6]))
    assert "nan" not in svg.lower() and len(_circles(svg)) == 2


def test_marker_radius_is_capped():
    svg = reaction_time_svg(_rt_responses([0.5], replays=40))
    assert max(r for _, _, r in _circles(svg)) <= 9.0


def test_heat_map_shades_by_share_of_the_row():
    from emognition.reports.common import heat_rgb

    # 2 of 2 and 8 of 8 correct are the same rate -> the same shade
    assert heat_rgb(2, 2, True) == heat_rgb(8, 8, True)
    assert heat_rgb(0, 5, False) is None and heat_rgb(1, 0, False) is None
    assert heat_rgb(1, 4, False) != heat_rgb(1, 4, True)       # red vs green
