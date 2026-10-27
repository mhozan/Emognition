# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the participant-window geometry helpers (ui/geometry.py, no PsychoPy)."""

import math

import pytest

from emognition.ui.geometry import fit_within, rounded_rect_vertices, star_vertices


def test_rounded_rect_spans_exactly_its_box():
    verts = rounded_rect_vertices(0.4, 0.14, 0.05, segments=8)
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    assert len(verts) == 4 * 9
    assert math.isclose(max(xs), 0.2) and math.isclose(min(xs), -0.2)
    assert math.isclose(max(ys), 0.07) and math.isclose(min(ys), -0.07)


def test_rounded_rect_runs_counter_clockwise():
    verts = rounded_rect_vertices(2.0, 1.0, 0.3)
    area2 = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(verts, verts[1:] + verts[:1]))
    assert area2 > 0                       # positive signed area = counter-clockwise


def test_rounded_rect_radius_is_clamped():
    pill = rounded_rect_vertices(1.0, 0.2, 5.0)       # radius capped at half the height
    assert math.isclose(max(v[1] for v in pill), 0.1)
    square = rounded_rect_vertices(1.0, 1.0, 0.0)
    assert len(square) == 4


@pytest.mark.parametrize("size, box, expected", [
    ((2560, 1600), (1920, 1200), (1920, 1200)),   # Retina framebuffer -> capped
    ((1280, 800), (1920, 1200), (1280, 800)),     # never enlarged
    ((3840, 2160), (1920, 1200), (1920, 1080)),   # 4K: limited by width
])
def test_fit_within(size, box, expected):
    assert fit_within(size, box) == expected


def test_fit_within_rejects_empty_sizes():
    with pytest.raises(ValueError):
        fit_within((0, 100), (10, 10))


def test_star_points_up_alternates_radii_and_runs_counter_clockwise():
    verts = star_vertices(1.0, 0.4)
    assert len(verts) == 10 and verts[0] == pytest.approx((0.0, 1.0))
    radii = [math.hypot(x, y) for x, y in verts]
    assert radii[0::2] == pytest.approx([1.0] * 5) and radii[1::2] == pytest.approx([0.4] * 5)
    area2 = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(verts, verts[1:] + verts[:1]))
    assert area2 > 0
