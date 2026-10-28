# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Generate the participant-screen button images into assets/images/.

Run with:  .venv/bin/python scripts/generate_buttons.py [--size 512] [--out DIR]

Two kinds: the emoticon faces (``<caption><emotion>.png``) and the replay
button (``replaybutton.png``).

The faces are the original Emognition artwork -- a 100 x 100 px bitmap set that
looked soft and jagged once scaled up to a modern screen -- redrawn as geometry,
so they're crisp at any size. Every stroke was measured from the originals: the
grey frame, the face circle, each face's own eye positions, the mouths (arcs, a
line, an ellipse) and the eyebrows. Two small tidy-ups: the frowns, which were
hand-drawn about 9 degrees askew, are symmetric, and every stroke has the same
weight. Drawn 4x larger, then shrunk with a Lanczos filter: smooth edges.

Captions use one type family across scripts, so the sets look alike:

* English and Spanish -- **Noto Sans Bold** (bundled with PsychoPy:
  ``psychopy/assets/fonts``);
* Chinese (Traditional, as in the original) -- **Noto Sans CJK TC Bold**
  (Debian/Ubuntu package ``fonts-noto-cjk``; or pass ``--cjk-font PATH``), the
  same weight as the Latin captions, so every set reads alike.

Both are SIL Open Font License; only the rendered PNGs ship with the app.

Caption sets, by file prefix (= emognition.ui.assets.Caption): 0 English,
1 Chinese, 2 none (the original default), 3 Spanish (Latin-American usage).

The replay button keeps the original's idea -- a dark tile with a circular arrow
and "REPLAY" -- drawn cleanly: a smooth clockwise ring ending in an arrowhead,
on a rounded tile whose corners are transparent, so it sits on any background.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

_REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, _REPO)

EMOTIONS = ("happy", "scared", "neutral", "sad", "angry")

# Caption sets: file prefix -> the word under each face (None: no caption).
CAPTIONS: dict[str, dict[str, str] | None] = {
    "0": {"happy": "happy", "scared": "scared", "neutral": "neutral", "sad": "sad", "angry": "angry"},
    "1": {"happy": "高興", "scared": "害怕", "neutral": "平靜", "sad": "傷心", "angry": "生氣"},
    "2": None,
    "3": {"happy": "feliz", "scared": "asustado", "neutral": "neutral", "sad": "triste", "angry": "enojado"},
}
CJK_CAPTIONS = {"1"}

# --- Geometry, in the original's 100 x 100 units (measured from the bitmaps) ---------

FRAME = (12.99, 8.73, 81.59, 76.51)      # the frame's centre line: left, top, right, bottom
FACE = (47.38, 42.76, 29.49)             # centre x, centre y, radius
STROKE = 1.0                             # every line
EYE_RADIUS = 2.37

# Per face: eye centres, optional eyebrows (two segments), and the mouth:
#   ("arc", cx, cy, r, from_deg, to_deg) -- degrees clockwise from 3 o'clock (y down)
#   ("line", (x0, y0), (x1, y1))
#   ("ellipse", cx, cy, rx, ry)
FACES = {
    "happy": {
        "eyes": ((37.32, 32.67), (55.32, 32.67)),
        "mouth": ("arc", 46.71, 45.93, 10.63, 11.1, 168.9),
    },
    "scared": {
        "eyes": ((37.90, 34.18), (55.90, 34.19)),
        "brows": (((34.22, 30.45), (39.75, 26.51)), ((53.05, 26.73), (58.83, 31.41))),
        "mouth": ("ellipse", 47.67, 57.70, 2.76, 3.72),
    },
    "neutral": {
        "eyes": ((36.66, 32.67), (54.66, 32.67)),
        "mouth": ("line", (38.50, 56.00), (56.50, 56.00)),
    },
    "sad": {
        "eyes": ((37.35, 33.38), (55.35, 33.38)),
        "mouth": ("arc", 48.55, 57.07, 10.53, -171.5, -8.5),
    },
    "angry": {
        "eyes": ((36.65, 35.34), (54.65, 35.34)),
        "brows": (((34.69, 26.94), (41.07, 32.12)), ((50.71, 31.13), (56.42, 27.04))),
        "mouth": ("arc", 47.25, 59.11, 10.37, -171.4, -8.6),
    },
}

# --- Colours and type ---------------------------------------------------------------

PAPER = (255, 255, 255)
INK = (0, 0, 0)                          # the face strokes
FRAME_GREY = (150, 150, 150)
TEXT = (28, 28, 28)                      # captions: near-black reads a touch softer
LATIN_SIZE = 13.0                        # one size for every Latin word ("asustado" is widest)
LATIN_BASELINE = 92.3
CJK_SIZE = 13.0
CJK_MIDDLE = 89.2                        # the glyphs' visual centre line
CAPTION_X = (FRAME[0] + FRAME[2]) / 2    # centred under the frame

SUPERSAMPLE = 4


def find_fonts(cjk_font: str | None = None) -> tuple[str, tuple[str, int]]:
    """(Noto Sans Bold path, (Noto Sans CJK TC Bold path, face index)); exits with a hint if missing."""
    import psychopy

    latin = os.path.join(os.path.dirname(psychopy.__file__), "assets", "fonts", "NotoSans-Bold.ttf")
    candidates = [cjk_font] if cjk_font else [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
    ]
    cjk = next((p for p in candidates if p and os.path.exists(p)), None)
    if not os.path.exists(latin) or cjk is None:
        sys.exit("Needs Noto Sans Bold (PsychoPy's assets) and Noto Sans CJK "
                 "(apt install fonts-noto-cjk, or --cjk-font PATH).")
    return latin, (cjk, _cjk_tc_index(cjk))


def _cjk_tc_index(path: str) -> int:
    """The Traditional Chinese face inside a Noto CJK collection (a plain font: 0)."""
    for index in range(10):
        try:
            if "TC" in ImageFont.truetype(path, 12, index=index).getname()[0].split():
                return index
        except OSError:
            break
    return 0


def _stroke(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], width: float) -> None:
    """A polyline with round joins and round ends (PIL's own ends are square)."""
    draw.line(points, fill=INK, width=round(width), joint="curve")
    r = width / 2.0
    for x, y in (points[0], points[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=INK)


def _arc_points(cx: float, cy: float, r: float, start: float, end: float, n: int = 240):
    return [(cx + r * math.cos(math.radians(start + (end - start) * i / n)),
             cy + r * math.sin(math.radians(start + (end - start) * i / n))) for i in range(n + 1)]


def draw_face(draw: ImageDraw.ImageDraw, emotion: str, k: float) -> None:
    """The frame, face and features of *emotion*, at *k* pixels per unit."""
    w = STROKE * k
    x0, y0, x1, y1 = (v * k for v in FRAME)
    draw.rectangle([x0 - w / 2, y0 - w / 2, x1 + w / 2, y1 + w / 2], outline=FRAME_GREY, width=round(w))
    cx, cy, r = (v * k for v in FACE)
    draw.ellipse([cx - r - w / 2, cy - r - w / 2, cx + r + w / 2, cy + r + w / 2], outline=INK, width=round(w))
    face = FACES[emotion]
    er = EYE_RADIUS * k
    for ex, ey in face["eyes"]:
        draw.ellipse([ex * k - er, ey * k - er, ex * k + er, ey * k + er], fill=INK)
    for a, b in face.get("brows", ()):
        _stroke(draw, [(a[0] * k, a[1] * k), (b[0] * k, b[1] * k)], w)
    kind, *spec = face["mouth"]
    if kind == "arc":
        mx, my, mr, start, end = spec
        _stroke(draw, _arc_points(mx * k, my * k, mr * k, start, end), w)
    elif kind == "line":
        (ax, ay), (bx, by) = spec
        _stroke(draw, [(ax * k, ay * k), (bx * k, by * k)], w)
    else:  # ellipse
        mx, my, rx, ry = (v * k for v in spec)
        draw.ellipse([mx - rx - w / 2, my - ry - w / 2, mx + rx + w / 2, my + ry + w / 2],
                     outline=INK, width=round(w))


def draw_caption(draw: ImageDraw.ImageDraw, text: str, cjk: bool, fonts, k: float) -> None:
    """*text* centred under the frame: Latin on a common baseline, CJK on its visual centre."""
    latin, (cjk_path, cjk_index) = fonts
    if cjk:
        font = ImageFont.truetype(cjk_path, CJK_SIZE * k, index=cjk_index)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font, anchor="ls")
        y = CJK_MIDDLE * k - (top + bottom) / 2.0
        draw.text((CAPTION_X * k - (left + right) / 2.0, y), text, font=font, fill=TEXT, anchor="ls")
    else:
        font = ImageFont.truetype(latin, LATIN_SIZE * k)
        draw.text((CAPTION_X * k, LATIN_BASELINE * k), text, font=font, fill=TEXT, anchor="ms")


def render(emotion: str, caption: str, size: int, fonts) -> Image.Image:
    """One emoticon button image, *size* x *size* px."""
    big = size * SUPERSAMPLE
    k = big / 100.0
    image = Image.new("RGB", (big, big), PAPER)
    draw = ImageDraw.Draw(image)
    draw_face(draw, emotion, k)
    words = CAPTIONS[caption]
    if words is not None:
        draw_caption(draw, words[emotion], caption in CJK_CAPTIONS, fonts, k)
    return image.resize((size, size), Image.Resampling.LANCZOS)


# The replay button: a dark indigo tile, white ring arrow and label (0..1 units).
REPLAY_TILE = (42, 39, 72, 255)
REPLAY_EDGE = (78, 72, 122, 255)
REPLAY_INK = (255, 255, 255, 255)
REPLAY_RING = (0.5, 0.42, 0.235)          # centre x, centre y, radius
REPLAY_ARC = (-25.0, 268.0)               # clockwise, degrees from 3 o'clock (y down)
REPLAY_STROKE = 0.068
REPLAY_LABEL_Y = 0.845                    # baseline of "REPLAY"
REPLAY_LABEL_SIZE = 0.165


def render_replay(size: int, fonts) -> Image.Image:
    """The replay button, *size* x *size* px RGBA (transparent outside the tile)."""
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad, radius = 0.02 * big, 0.2 * big
    draw.rounded_rectangle([pad, pad, big - pad, big - pad], radius=radius, fill=REPLAY_EDGE)
    edge = 0.018 * big
    draw.rounded_rectangle([pad + edge, pad + edge, big - pad - edge, big - pad - edge],
                           radius=radius - edge, fill=REPLAY_TILE)

    cx, cy, r = (v * big for v in REPLAY_RING)
    start, end = REPLAY_ARC
    width = REPLAY_STROKE * big
    # A thick ring is drawn as one arc (a wide polyline of many short segments
    # leaves a saw-toothed edge at this weight), with a round cap at its tail.
    outer = r + width / 2
    draw.arc([cx - outer, cy - outer, cx + outer, cy + outer], start, end,
             fill=REPLAY_INK, width=round(width))
    tail = (cx + r * math.cos(math.radians(start)), cy + r * math.sin(math.radians(start)))
    draw.ellipse([tail[0] - width / 2, tail[1] - width / 2, tail[0] + width / 2, tail[1] + width / 2],
                 fill=REPLAY_INK)
    # Arrowhead at the arc's end, pointing along the clockwise tangent.
    theta = math.radians(end)
    px, py = cx + r * math.cos(theta), cy + r * math.sin(theta)
    tx, ty = -math.sin(theta), math.cos(theta)        # clockwise tangent (y down)
    nx, ny = math.cos(theta), math.sin(theta)         # outward normal
    length, half = 0.14 * big, 0.105 * big
    tip = (px + tx * length * 0.75, py + ty * length * 0.75)
    back = (px - tx * length * 0.25, py - ty * length * 0.25)
    draw.polygon([tip, (back[0] + nx * half, back[1] + ny * half),
                  (back[0] - nx * half, back[1] - ny * half)], fill=REPLAY_INK)

    latin = fonts[0]
    font = ImageFont.truetype(latin, REPLAY_LABEL_SIZE * big)
    draw.text((0.5 * big, REPLAY_LABEL_Y * big), "REPLAY", font=font, fill=REPLAY_INK, anchor="ms")
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--size", type=int, default=512, help="image size in px (default 512)")
    parser.add_argument("--out", default=os.path.join(_REPO, "assets", "images"),
                        help="output folder (default: assets/images)")
    parser.add_argument("--cjk-font", default=None, help="a Noto Sans CJK (or other TC) font file")
    args = parser.parse_args(argv)
    fonts = find_fonts(args.cjk_font)
    os.makedirs(args.out, exist_ok=True)
    for caption in CAPTIONS:
        for emotion in EMOTIONS:
            path = os.path.join(args.out, f"{caption}{emotion}.png")
            render(emotion, caption, args.size, fonts).save(path, optimize=True)
            print(f"wrote {path}")
    path = os.path.join(args.out, "replaybutton.png")
    render_replay(args.size, fonts).save(path, optimize=True)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
