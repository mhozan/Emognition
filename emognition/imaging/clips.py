# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""One small picture per recording, for checking a stimulus set at a glance.

Top: the waveform, on a fixed full-scale axis (so levels and clipping compare
from card to card). Middle: the spectrogram (0-8 kHz, a 70 dB range). Bottom:
the short-time RMS curve the endpoint detector worked from, on a fixed
-70..0 dBFS scale, with the detector's threshold dashed. The
detected speech is shaded on both, and clipped samples are marked in red. All
cards share one time scale (the longest clip's), so an odd duration stands out.

Pillow + numpy only, so the cards can be drawn on a worker thread.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from ..audio.analysis import SPEC_RANGE_DB, ClipAnalysis, ClipStats

# A perceptual "magma" ramp (dark -> bright), interpolated from 9 stops.
_MAGMA = np.array([
    (0, 0, 4), (28, 16, 68), (79, 18, 123), (129, 37, 129), (181, 54, 122),
    (229, 80, 100), (251, 135, 97), (254, 194, 135), (252, 253, 191),
], dtype=np.float64)
_LUT = np.stack([np.interp(np.linspace(0, 1, 256), np.linspace(0, 1, len(_MAGMA)), _MAGMA[:, c])
                 for c in range(3)], axis=1).astype(np.uint8)

CURVE_FLOOR_DB = -70.0
_PAPER = (251, 251, 254)
_GRID = (226, 226, 236)
_CURVE = (60, 52, 150)
_THRESHOLD = (150, 150, 170)
_SPEECH = (108, 92, 231)          # the theme accent
_OUTSIDE = (232, 232, 238)        # past the end of this clip (shorter than the longest)
_CLIPPED = (214, 48, 49)
_WAVE = (84, 72, 196)


def spectrogram_image(analysis: ClipAnalysis, width: int, height: int, span: float) -> Image.Image:
    """The spectrogram drawn over *span* seconds (blank beyond the clip's end)."""
    level = (analysis.spectrogram_db + SPEC_RANGE_DB) / SPEC_RANGE_DB       # 0..1
    rgb = _LUT[np.clip((level * 255).astype(int), 0, 255)][::-1]           # low frequencies at the bottom
    clip_w = max(1, round(width * min(1.0, analysis.duration / span)))
    image = Image.new("RGB", (width, height), _OUTSIDE)
    image.paste(Image.fromarray(rgb).resize((clip_w, height), Image.Resampling.BILINEAR), (0, 0))
    return image


def curve_image(analysis: ClipStats, width: int, height: int, span: float) -> Image.Image:
    """The RMS curve, threshold and speech span over *span* seconds."""
    image = Image.new("RGB", (width, height), _PAPER)
    draw = ImageDraw.Draw(image)

    def x(t: float) -> float:
        return t / span * (width - 1)

    def y(level_db: float) -> float:
        return (1.0 - (max(level_db, CURVE_FLOOR_DB) - CURVE_FLOOR_DB) / -CURVE_FLOOR_DB) * (height - 1)

    end = x(analysis.duration)
    if end < width - 1:
        draw.rectangle((end, 0, width, height), fill=_OUTSIDE)
    for level_db in (-20.0, -40.0, -60.0):
        draw.line((0, y(level_db), end, y(level_db)), fill=_GRID)
    draw.rectangle((x(analysis.onset), 0, x(analysis.offset), height), fill=(234, 231, 252))
    threshold = y(analysis.threshold_db)
    for start in range(0, int(end), 8):                              # dashed
        draw.line((start, threshold, min(start + 4, end), threshold), fill=_THRESHOLD)
    if analysis.times.size > 1:
        points = [(x(t), y(v)) for t, v in zip(analysis.times, analysis.rms_curve_db)]
        draw.line(points, fill=_CURVE, width=2)
    for t in (analysis.onset, analysis.offset):
        draw.line((x(t), 0, x(t), height), fill=_SPEECH, width=2)
    if analysis.clipped:
        draw.rectangle((0, 0, width, 3), fill=_CLIPPED)
    return image


def waveform_image(analysis: ClipStats, width: int, height: int, span: float) -> Image.Image:
    """The waveform's outline (min..max per pixel column) on a fixed -1..1 axis."""
    image = Image.new("RGB", (width, height), _PAPER)
    draw = ImageDraw.Draw(image)
    end = round((width - 1) * min(1.0, analysis.duration / span))
    if end < width - 1:
        draw.rectangle((end + 1, 0, width, height), fill=_OUTSIDE)
    mid = (height - 1) / 2.0
    draw.line((0, mid, end, mid), fill=_GRID)
    n = analysis.wave_min.size
    for col in range(end + 1):                                       # one column per pixel
        a = int(col / max(end, 1) * (n - 1))
        b = max(a + 1, int((col + 1) / max(end, 1) * (n - 1)))
        lo, hi = float(analysis.wave_min[a:b].min()), float(analysis.wave_max[a:b].max())
        draw.line((col, mid - hi * mid, col, mid - lo * mid), fill=_WAVE)
    if analysis.clipped:
        draw.rectangle((0, 0, width, 2), fill=_CLIPPED)
        draw.rectangle((0, height - 3, width, height), fill=_CLIPPED)
    return image


def clip_card(analysis: ClipAnalysis, width: int = 300, height: int = 160,
              span: float | None = None) -> Image.Image:
    """Waveform, spectrogram and RMS curve (22 / 45 / 33 %), over *span* s (default: this clip)."""
    span = max(span or analysis.duration, 1e-3)
    h_wave = round(height * 0.22)
    h_spec = round(height * 0.45)
    card = Image.new("RGB", (width, height), _PAPER)
    card.paste(waveform_image(analysis, width, h_wave, span), (0, 0))
    spec = spectrogram_image(analysis, width, h_spec, span)
    draw = ImageDraw.Draw(spec)
    for t in (analysis.onset, analysis.offset):                      # the speech span, there too
        xt = t / span * (width - 1)
        draw.line((xt, 0, xt, h_spec), fill=(255, 255, 255), width=1)
    card.paste(spec, (0, h_wave))
    card.paste(curve_image(analysis, width, height - h_wave - h_spec, span), (0, h_wave + h_spec))
    return card
