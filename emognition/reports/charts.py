# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Hand-built SVG charts (no plotting library) for embedding in the HTML report.

This revives the reaction-time scatter from the original ``monitorperf.m``: one
point per trial, marker size growing with the number of replays, coloured by
correctness, with a faint line tracing the sequence.

Two ideas worth internalising if SVG is new to you:

1. **SVG's y-axis points down.** (0,0) is the top-left corner, y increases
   downward. So to put large reaction times near the top of the plot we invert:
   ``py = top + (ymax - value) / (ymax - ymin) * plot_height``.
2. **A chart is just linear maps.** Each axis is a function from data-space
   (trial number, seconds) to pixel-space. Everything else is bookkeeping. We
   keep those maps in tiny closures (:func:`_linear_map`) so the drawing code
   reads like the maths.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from html import escape

from ..core import Response
from ..core.scoring import DEFAULT_RT_KIND

# Plot colours (match the HTML theme / confusion heat-map).
_CORRECT = "#5ad17a"
_INCORRECT = "#ff7b7b"
_LINE = "#7c6cff"
_AXIS = "#9aa0c7"
_GRID = "#2a2e52"
# Markers grow with replays but stay readable (a 20-replay trial used to cover the plot).
_MAX_RADIUS = 9.0


def _linear_map(d0: float, d1: float, p0: float, p1: float) -> Callable[[float], float]:
    """Return f mapping data range [d0,d1] linearly onto pixel range [p0,p1]."""
    span = (d1 - d0) or 1.0  # guard against a zero-width domain
    scale = (p1 - p0) / span
    return lambda v: p0 + (v - d0) * scale


def _nice_ticks(lo: float, hi: float, count: int = 4) -> list[float]:
    """A handful of evenly spaced tick values across [lo, hi]."""
    if hi <= lo:
        return [lo]
    step = (hi - lo) / count
    return [lo + step * i for i in range(count + 1)]


def reaction_time_svg(
    responses: Sequence[Response],
    *,
    rt_kind: str = DEFAULT_RT_KIND,
    width: int = 720,
    height: int = 260,
) -> str:
    """Return an inline ``<svg>`` reaction-time chart for *responses*.

    X = trial number, Y = reaction time (the chosen ``rt_kind``). Points are
    green when correct, red when wrong; marker radius grows with replays.
    Unanswered trials (no RT) and non-finite values are skipped. Returns a small
    "no data" placeholder SVG if nothing is plottable.
    """
    rt_attr = "rt_onset" if rt_kind == "onset" else "rt_offset"
    points = [
        (i, rt, r.is_correct, r.n_replays)
        for i, r in enumerate(responses, start=1)
        if (rt := getattr(r, rt_attr)) is not None and math.isfinite(rt)
    ]
    if not points:
        return (
            f"<svg viewBox='0 0 {width} {height}' role='img' "
            f"aria-label='No reaction-time data'>"
            f"<text x='{width/2}' y='{height/2}' fill='{_AXIS}' "
            f"text-anchor='middle'>no reaction-time data</text></svg>"
        )

    margin = {"left": 52, "right": 16, "top": 16, "bottom": 36}
    plot_w = width - margin["left"] - margin["right"]
    plot_h = height - margin["top"] - margin["bottom"]
    left, top = margin["left"], margin["top"]

    n = len(responses)
    rts = [rt for _, rt, _, _ in points]
    # Always include 0, then pad the span (a negative max used to put ymax below
    # the highest point, and a single negative RT inverted the axis).
    lo, hi = min(0.0, min(rts)), max(0.0, max(rts))
    pad = 0.08 * (hi - lo) or 1.0
    ymin = lo - pad if lo < 0 else 0.0
    ymax = hi + pad

    x_of = _linear_map(0.5, n + 0.5, left, left + plot_w)
    y_of = _linear_map(ymin, ymax, top + plot_h, top)  # inverted: data-up = pixel-up

    parts: list[str] = [
        f"<svg viewBox='0 0 {width} {height}' role='img' "
        f"aria-label='Reaction time per trial' font-family='system-ui,sans-serif' "
        f"font-size='11'>"
    ]

    # y grid + ticks
    for tick in _nice_ticks(ymin, ymax):
        py = y_of(tick)
        parts.append(
            f"<line x1='{left}' y1='{py:.1f}' x2='{left + plot_w}' y2='{py:.1f}' "
            f"stroke='{_GRID}'/>"
        )
        parts.append(
            f"<text x='{left - 6}' y='{py + 3:.1f}' fill='{_AXIS}' "
            f"text-anchor='end'>{tick:.2f}</text>"
        )

    # axes
    parts.append(
        f"<line x1='{left}' y1='{top}' x2='{left}' y2='{top + plot_h}' "
        f"stroke='{_AXIS}'/>"
        f"<line x1='{left}' y1='{top + plot_h}' x2='{left + plot_w}' "
        f"y2='{top + plot_h}' stroke='{_AXIS}'/>"
    )

    # connecting line
    poly = " ".join(f"{x_of(i):.1f},{y_of(rt):.1f}" for i, rt, _, _ in points)
    parts.append(f"<polyline points='{poly}' fill='none' stroke='{_LINE}' opacity='0.5'/>")

    # points (radius grows with replays)
    for i, rt, correct, replays in points:
        cx, cy = x_of(i), y_of(rt)
        radius = min(3 + 1.8 * replays, _MAX_RADIUS)
        colour = _CORRECT if correct else _INCORRECT
        parts.append(
            f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='{radius:.1f}' "
            f"fill='{colour}' fill-opacity='0.85'/>"
        )

    # axis labels
    parts.append(
        f"<text x='{left + plot_w / 2}' y='{height - 6}' fill='{_AXIS}' "
        f"text-anchor='middle'>Trial #</text>"
    )
    parts.append(
        f"<text x='14' y='{top + plot_h / 2}' fill='{_AXIS}' text-anchor='middle' "
        f"transform='rotate(-90 14 {top + plot_h / 2:.1f})'>RT from {escape(rt_kind)} (s)</text>"
    )

    parts.append("</svg>")
    return "".join(parts)
