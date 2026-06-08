# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the hand-built SVG reaction-time chart."""

import xml.dom.minidom as minidom

from emognition.core import Emotion, Gender, Response, Stimulus
from emognition.reports import reaction_time_svg


def _resp(responded, rt_offset, n_replays=0):
    stim = Stimulus(path="x_hap_f.wav", emotion=Emotion.HAPPY, gender=Gender.FEMALE)
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
