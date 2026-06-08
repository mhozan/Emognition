# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Matplotlib figures (as PNG bytes) for the PDF report.

The HTML report draws its own SVG; the PDF needs raster images, so these render
with matplotlib. We force the **Agg** backend (no display, no GUI toolkit) before
importing pyplot -- essential for headless/automated report generation and for
not colliding with PsychoPy's GL window.
"""

from __future__ import annotations

import io
from collections.abc import Sequence

import matplotlib

matplotlib.use("Agg")  # headless raster backend; must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402

from ..core import Response, SessionSummary  # noqa: E402


def _to_png(fig) -> bytes:
    """Serialise a figure to PNG bytes and close it (free the memory)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def confusion_png(summary: SessionSummary) -> bytes:
    """Confusion-matrix heatmap (rows = true emotion, cols = chosen)."""
    labels = [e.label for e in summary.emotion_order]
    data = summary.confusion

    fig, ax = plt.subplots(figsize=(4.2, 3.6))
    im = ax.imshow(data, cmap="Greens")
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="left")
    ax.set_yticks(range(len(labels)), labels)
    ax.xaxis.set_label_position("top")
    ax.xaxis.tick_top()
    ax.set_xlabel("chosen")
    ax.set_ylabel("true")
    vmax = max((max(r) for r in data), default=0)
    for i, row in enumerate(data):
        for j, n in enumerate(row):
            ax.text(j, i, str(n), ha="center", va="center",
                    color="white" if (vmax and n > vmax / 2) else "black", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.8)
    return _to_png(fig)


def reaction_time_png(responses: Sequence[Response]) -> bytes:
    """Two stacked scatter/line plots: RT from offset (top) and onset (bottom)."""
    fig, axes = plt.subplots(2, 1, figsize=(6.2, 5.0), sharex=True)
    for ax, attr, title in (
        (axes[0], "rt_offset", "Reaction time from audio offset (default)"),
        (axes[1], "rt_onset", "Reaction time from audio onset"),
    ):
        xs, ys, colors = [], [], []
        for i, r in enumerate(responses, start=1):
            val = getattr(r, attr)
            if val is None:
                continue
            xs.append(i)
            ys.append(val)
            colors.append("#2e7d32" if r.is_correct else "#c62828")
        if xs:
            ax.plot(xs, ys, "-", color="#7c6cff", alpha=0.5, zorder=1)
            ax.scatter(xs, ys, c=colors, s=28, zorder=2)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel("RT (s)")
        ax.grid(True, alpha=0.3)
    axes[1].set_xlabel("Trial #")
    return _to_png(fig)
