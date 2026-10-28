# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Generate the small control icons the Qt theme uses into assets/images/ui/.

Run with:  .venv/bin/python scripts/generate_ui_icons.py

A Qt stylesheet that restyles a checkbox, a dropdown or a spin box must also
supply its check mark and arrows as images -- otherwise Qt draws none, and the
control looks inert (unchecked boxes vanished; dropdowns had no arrow). Each
icon is drawn 8x supersampled at 1x and 2x (``name@2x.png``, which Qt picks on
high-DPI screens). Colours follow emognition/ui/theme.py.
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from emognition.ui.assets import ui_icon_path  # noqa: E402

WHITE = (255, 255, 255, 255)
MUTED = (90, 90, 122, 255)        # theme.MUTED
DISABLED = (163, 163, 184, 255)   # theme.DISABLED
SUPERSAMPLE = 8

# name -> (size in px at 1x, polyline points in 0..1 units, colour, stroke as a fraction of size)
ICONS = {
    "check": (14, [(0.20, 0.53), (0.42, 0.74), (0.81, 0.28)], WHITE, 0.15),
    "arrow-down": (10, [(0.15, 0.32), (0.50, 0.68), (0.85, 0.32)], MUTED, 0.16),
    "arrow-down-disabled": (10, [(0.15, 0.32), (0.50, 0.68), (0.85, 0.32)], DISABLED, 0.16),
    "arrow-up": (10, [(0.15, 0.68), (0.50, 0.32), (0.85, 0.68)], MUTED, 0.16),
    "arrow-up-disabled": (10, [(0.15, 0.68), (0.50, 0.32), (0.85, 0.68)], DISABLED, 0.16),
}


def render(size: int, points, color, stroke: float) -> Image.Image:
    """A round-capped polyline on a transparent square, *size* px."""
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pts = [(x * big, y * big) for x, y in points]
    width = stroke * big
    draw.line(pts, fill=color, width=round(width), joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> int:
    os.makedirs(os.path.dirname(ui_icon_path("check")), exist_ok=True)
    for name, (size, points, color, stroke) in ICONS.items():
        for scale, suffix in ((1, ""), (2, "@2x")):
            path = ui_icon_path(name + suffix)
            render(size * scale, points, color, stroke).save(path, optimize=True)
            print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
