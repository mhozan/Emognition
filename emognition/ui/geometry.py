# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Small pure-geometry helpers for the participant window (no PsychoPy import).

Kept apart from the drawing code so the arithmetic is testable headless, and so
shapes are computed once (PsychoPy tessellates a ShapeStim when its vertices are
set; reusing precomputed vertices keeps that out of the frame loop).
"""

from __future__ import annotations

import math


def rounded_rect_vertices(
    width: float,
    height: float,
    radius: float,
    *,
    segments: int = 8,
) -> list[tuple[float, float]]:
    """Outline of a *width* x *height* rectangle with rounded corners, centred on 0.

    Vertices run counter-clockwise starting at the top-right corner; each corner
    arc uses ``segments`` steps. The radius is clamped so it never exceeds half
    of either side (a pill shape at most).
    """
    half_w, half_h = width / 2.0, height / 2.0
    r = max(0.0, min(radius, half_w, half_h))
    if r == 0.0:
        return [(half_w, half_h), (-half_w, half_h), (-half_w, -half_h), (half_w, -half_h)]
    corners = [                       # (arc centre x, arc centre y, start angle in degrees)
        (half_w - r, half_h - r, 0.0),
        (-half_w + r, half_h - r, 90.0),
        (-half_w + r, -half_h + r, 180.0),
        (half_w - r, -half_h + r, 270.0),
    ]
    vertices: list[tuple[float, float]] = []
    for cx, cy, start in corners:
        for step in range(segments + 1):
            angle = math.radians(start + 90.0 * step / segments)
            vertices.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return vertices


def fit_within(size: tuple[float, float], box: tuple[float, float]) -> tuple[int, int]:
    """Scale *size* down (never up) to fit inside *box*, keeping its aspect ratio.

    Used to cap background textures: calm pictures don't need 4K/Retina detail,
    and a smaller texture decodes and uploads faster (the GPU scales it smoothly).
    """
    w, h = float(size[0]), float(size[1])
    if w <= 0 or h <= 0:
        raise ValueError(f"size must be positive, got {size}")
    scale = min(1.0, box[0] / w, box[1] / h)
    return max(1, round(w * scale)), max(1, round(h * scale))
