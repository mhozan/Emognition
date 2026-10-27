# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The progress-star row, rendered as one transparent picture.

Drawn as separate PsychoPy shapes, every star cost about 0.14 ms of *every*
frame: 24 stars took a frame from 3.3 to 6.5 ms and dropped frames, which would
coarsen the reaction times. As one texture, the whole row is a single draw,
however long it is. It only changes between trials, when a star is earned, so
re-rendering it then costs nothing that's timed.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..ui.geometry import star_vertices

GOLD = (255, 214, 40)
EMPTY = (72, 72, 72)
_FILL = 0.42          # star radius as a fraction of its square cell
_SUPERSAMPLE = 4      # drawn 4x larger, then shrunk: smooth edges


def star_row(
    slots: int,
    earned: int,
    slot_px: int,
    *,
    gold: tuple[int, int, int] = GOLD,
    empty: tuple[int, int, int] = EMPTY,
) -> Image.Image:
    """*slots* stars side by side, the first *earned* gold and the rest grey.

    Returns an RGBA strip ``slots * slot_px`` wide and ``slot_px`` high, clear
    around the stars, so it sits on any background.

    Raises:
        ValueError: for no slots or a non-positive cell size.
    """
    if slots <= 0 or slot_px <= 0:
        raise ValueError(f"need at least one slot of at least 1 px, got {slots} x {slot_px}")
    cell = slot_px * _SUPERSAMPLE
    image = Image.new("RGBA", (slots * cell, cell), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    outline = star_vertices(_FILL * cell)
    for k in range(slots):
        cx, cy = (k + 0.5) * cell, 0.5 * cell
        color = gold if k < earned else empty
        draw.polygon([(cx + x, cy - y) for x, y in outline], fill=(*color, 255))
    # Pillow resizes RGBA with premultiplied alpha, so the edges don't darken.
    return image.resize((slots * slot_px, slot_px), Image.Resampling.LANCZOS)
