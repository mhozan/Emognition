# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Generate the bundled participant-window backgrounds into assets/backgrounds/.

Run with:  .venv/bin/python scripts/generate_backgrounds.py [OUT_DIR]

The pictures are drawn procedurally (numpy + Pillow, fixed seeds), so they are
reproducible, licence-clean (no third-party art) and easy to tweak. Design rules,
because these sit behind an emotion-recognition task:

* calm and static -- soft shapes, low contrast, no motion;
* no text and **no faces or characters** (a face could prime emotion judgements);
* mid-dark, so the white prompt, key numbers and emoticon tiles stay readable;
* decoration kept to the edges and bottom: the prompt (centre-left) and the
  response column (right of centre) sit over smooth areas.

The default background (a calm gradient) is *not* generated here: the app renders
it at runtime at the exact window size (emognition.imaging.calm_gradient).
"""

from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from emognition.imaging import DEFAULT_MAX_LUMA, cap_luminance, mean_luminance  # noqa: E402
from emognition.ui.assets import backgrounds_dir, background_path  # noqa: E402

W, H = 1920, 1080

# Where the experiment draws things (pixels on a 1920x1080 frame), padded: keep
# these areas smooth so nothing busy sits behind text or buttons.
_KEEP_CLEAR = [
    (1270, 90, 1650, 990),    # number labels + emoticon column
    (470, 400, 1130, 580),    # prompt text
    (600, 30, 1320, 100),     # progress bar
]


# --------------------------------------------------------------------------
# drawing helpers
# --------------------------------------------------------------------------

def _gradient(stops: list[tuple[float, tuple[int, int, int]]]) -> np.ndarray:
    """Vertical colour gradient through (position 0..1, RGB) stops -> float (H, W, 3)."""
    y = np.linspace(0.0, 1.0, H)
    pos = [p for p, _ in stops]
    rows = np.stack([np.interp(y, pos, [c[i] for _, c in stops]) for i in range(3)], axis=1)
    return np.broadcast_to(rows[:, None, :], (H, W, 3)).astype(np.float32).copy()


def _glow(rgb: np.ndarray, center, radius: float, color, strength: float) -> None:
    """Blend a soft radial glow of *color* into *rgb* in place."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d2 = (xx - center[0]) ** 2 + (yy - center[1]) ** 2
    weight = (strength * np.exp(-d2 / (2.0 * radius * radius)))[..., None]
    rgb += weight * (np.asarray(color, dtype=np.float32) - rgb)


def _clear(x: float, y: float, margin: float = 0.0) -> bool:
    """True if (x, y) is outside every keep-clear area (plus *margin* px)."""
    return all(not (x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin)
               for x0, y0, x1, y1 in _KEEP_CLEAR)


def _layer(color=(255, 255, 255)) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """A transparent drawing layer whose hidden RGB is already *color*.

    Blurring averages RGB as well as alpha; on a layer of transparent *black* the
    soft edges would pick up a dark fringe. Pre-filling the RGB with the shape's
    own colour keeps blurred edges clean (draw one colour family per layer).
    """
    img = Image.new("RGBA", (W, H), tuple(color[:3]) + (0,))
    return img, ImageDraw.Draw(img)


def _composite(base: Image.Image, layer: Image.Image, blur: float = 0.0) -> Image.Image:
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(base.convert("RGBA"), layer)


def _to_image(rgb: np.ndarray, seed: int) -> Image.Image:
    """Quantise to 8 bits with triangular dither (hides banding in smooth skies)."""
    rng = np.random.default_rng(seed)
    noise = rng.random((H, W, 1), dtype=np.float32) - rng.random((H, W, 1), dtype=np.float32)
    return Image.fromarray(np.clip(np.rint(rgb + noise), 0, 255).astype(np.uint8))


def _wave(x: np.ndarray, base: float, parts: list[tuple[float, float, float]]) -> np.ndarray:
    """A smooth horizon line: *base* plus a sum of (amplitude, wavelength, phase) sines."""
    y = np.full_like(x, base, dtype=np.float64)
    for amp, wavelength, phase in parts:
        y += amp * np.sin(2 * np.pi * x / wavelength + phase)
    return y


def _fill_below(draw: ImageDraw.ImageDraw, ys: np.ndarray, color) -> None:
    xs = np.linspace(0, W, len(ys))
    draw.polygon([(0, H)] + list(zip(xs.tolist(), ys.tolist())) + [(W, H)], fill=color)


# --------------------------------------------------------------------------
# scenes
# --------------------------------------------------------------------------

def starry_night() -> Image.Image:
    rgb = _gradient([(0.0, (12, 18, 48)), (0.6, (22, 32, 78)), (1.0, (30, 44, 96))])
    _glow(rgb, (300, 210), 170, (120, 140, 210), 0.35)          # moonlight halo
    img = _to_image(rgb, seed=101).convert("RGBA")

    rng = np.random.default_rng(1)
    stars, draw = _layer((235, 235, 255))
    placed = 0
    while placed < 120:
        x, y = rng.uniform(0, W), rng.uniform(0, H) ** 1.0 * rng.uniform(0.15, 1.0)
        if y > 880 or not _clear(x, y, margin=40):
            continue
        r = rng.uniform(0.9, 2.4)
        a = int(rng.uniform(120, 230))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(235, 235, 255, a))
        placed += 1
    img = _composite(img, stars, blur=0.9)

    sparkles, draw = _layer((220, 225, 255))                    # a few softly glowing stars
    for x, y in [(120, 90), (520, 170), (760, 300), (210, 470), (980, 140), (1750, 70)]:
        draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(220, 225, 255, 70))
    img = _composite(img, sparkles, blur=4)

    moon, draw = _layer((238, 236, 214))
    draw.ellipse((300 - 44, 210 - 44, 300 + 44, 210 + 44), fill=(238, 236, 214, 255))
    img = _composite(img, moon, blur=1.5)

    xs = np.linspace(0, W, 400)                                 # far-away dark hills
    for base, parts, color in [(965, [(22, 900, 0.4), (10, 380, 1.9)], (18, 28, 64)),
                               (1010, [(18, 700, 2.2), (8, 260, 0.3)], (13, 21, 50))]:
        hill, draw = _layer(color)
        _fill_below(draw, _wave(xs, base, parts), color + (255,))
        img = _composite(img, hill, blur=1.2)
    return img.convert("RGB")


def under_the_sea() -> Image.Image:
    rgb = _gradient([(0.0, (26, 96, 132)), (0.5, (18, 70, 110)), (1.0, (10, 40, 78))])
    img = _to_image(rgb, seed=202).convert("RGBA")

    rays, draw = _layer((210, 240, 255))                        # slanted light from the surface
    for x_top, spread, alpha in [(120, 150, 22), (560, 120, 16), (980, 140, 14), (1460, 120, 16)]:
        draw.polygon([(x_top - 45, 0), (x_top + 45, 0),
                      (x_top + 420 + spread, H), (x_top + 420 - spread, H)],
                     fill=(210, 240, 255, alpha))
    img = _composite(img, rays, blur=45)

    sand, draw = _layer((150, 128, 90))
    xs = np.linspace(0, W, 300)
    _fill_below(draw, _wave(xs, 1032, [(10, 640, 0.7), (5, 230, 2.1)]), (150, 128, 90, 190))
    img = _composite(img, sand, blur=5)

    weed, draw = _layer((22, 96, 86))                           # a few strands at the far left
    for base_x, height, phase in [(40, 330, 0.0), (95, 250, 1.2), (150, 190, 2.4)]:
        ys = np.linspace(H, H - height, 60)
        xs_w = base_x + 14 * np.sin(np.linspace(0, 3 * np.pi, 60) + phase)
        draw.line(list(zip(xs_w.tolist(), ys.tolist())), fill=(22, 96, 86, 150), width=13)
    img = _composite(img, weed, blur=2.5)

    rng = np.random.default_rng(2)
    bubbles, draw = _layer((220, 245, 255))
    placed = 0
    while placed < 24:
        x = rng.choice([rng.uniform(20, 420), rng.uniform(420, 1250)], p=[0.7, 0.3])
        y = rng.uniform(140, 1020)
        r = rng.uniform(7, 34)
        if not _clear(x, y, margin=r + 30):
            continue
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(200, 235, 255, 26),
                     outline=(220, 245, 255, 90), width=max(2, int(r / 9)))
        hr = r * 0.25
        draw.ellipse((x - r * 0.45 - hr, y - r * 0.45 - hr, x - r * 0.45 + hr, y - r * 0.45 + hr),
                     fill=(240, 250, 255, 120))
        placed += 1
    return _composite(img, bubbles, blur=0.8).convert("RGB")


def rolling_hills() -> Image.Image:
    rgb = _gradient([(0.0, (40, 44, 96)), (0.5, (78, 70, 124)),
                     (0.72, (118, 94, 128)), (1.0, (118, 94, 128))])
    _glow(rgb, (330, 760), 230, (220, 160, 140), 0.30)          # low sun behind the hills
    img = _to_image(rgb, seed=303).convert("RGBA")

    clouds, draw = _layer((235, 220, 240))
    for cx, cy, s in [(260, 150, 1.0), (640, 230, 0.7), (1020, 120, 0.55)]:
        for dx, dy, rx, ry in [(-70, 10, 90, 34), (0, -12, 110, 44), (80, 8, 85, 32)]:
            draw.ellipse((cx + dx * s - rx * s, cy + dy * s - ry * s,
                          cx + dx * s + rx * s, cy + dy * s + ry * s), fill=(235, 220, 240, 40))
    img = _composite(img, clouds, blur=16)

    xs = np.linspace(0, W, 400)
    for base, parts, color in [(760, [(40, 1500, 0.3), (18, 520, 1.7)], (70, 100, 110)),
                               (840, [(36, 1100, 2.0), (14, 430, 0.6)], (48, 86, 88)),
                               (935, [(30, 1300, 4.1), (12, 360, 2.8)], (32, 68, 66))]:
        hill, draw = _layer(color)
        _fill_below(draw, _wave(xs, base, parts), color + (255,))
        img = _composite(img, hill, blur=1.5)
    return img.convert("RGB")


def soft_bubbles() -> Image.Image:
    rgb = _gradient([(0.0, (46, 42, 106)), (1.0, (30, 72, 114))])
    _glow(rgb, (1350, 260), 420, (96, 86, 170), 0.35)
    img = _to_image(rgb, seed=404).convert("RGBA")

    palette = [(255, 182, 213), (190, 170, 255), (150, 210, 255), (180, 240, 220)]
    rng = np.random.default_rng(4)
    layers = {c: _layer(c) for c in palette}
    for _ in range(26):
        x, y = rng.uniform(-60, W + 60), rng.uniform(-60, H + 60)
        r = rng.uniform(50, 170)
        alpha = int(rng.uniform(16, 38) * (0.45 if not _clear(x, y) else 1.0))
        color = palette[int(rng.integers(len(palette)))]
        layers[color][1].ellipse((x - r, y - r, x + r, y + r), fill=color + (alpha,))
    for layer, _draw in layers.values():
        img = _composite(img, layer, blur=26)
    return img.convert("RGB")


def classic_purple() -> Image.Image:
    """The original MATLAB background (background_main.jpg), dimmed for white text."""
    with Image.open(background_path()) as src:
        img = src.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
    return cap_luminance(img, 0.40)


# --------------------------------------------------------------------------
# more helpers (for scenes 06-30)
# --------------------------------------------------------------------------

def _stars(img: Image.Image, n: int, seed: int, *, y_max: float = H, size=(0.8, 2.2),
           alpha=(110, 220), color=(235, 235, 255), blur: float = 0.8) -> Image.Image:
    """*n* small stars outside the keep-clear areas, above *y_max*."""
    rng = np.random.default_rng(seed)
    layer, draw = _layer(color)
    placed = 0
    while placed < n:
        x, y = rng.uniform(0, W), rng.uniform(0, y_max)
        if not _clear(x, y, margin=30):
            continue
        r = rng.uniform(*size)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=tuple(color) + (int(rng.uniform(*alpha)),))
        placed += 1
    return _composite(img, layer, blur=blur)


def _ridge(xs: np.ndarray, base: float, rough: float, seed: int, smooth: int = 15) -> np.ndarray:
    """A natural mountain ridge line: a smoothed random walk around *base*."""
    rng = np.random.default_rng(seed)
    walk = np.cumsum(rng.normal(0.0, rough, xs.size))
    walk -= np.linspace(walk[0], walk[-1], xs.size)              # no overall tilt
    kernel = np.ones(smooth) / smooth
    return base + np.convolve(walk - walk.mean(), kernel, mode="same")


def _blobs(img: Image.Image, palette, n: int, seed: int, rmin: float, rmax: float,
           alpha=(16, 38), blur: float = 26, where=None) -> Image.Image:
    """Soft translucent discs (bokeh, cloud puffs, nebulae), fainter over keep-clear areas."""
    rng = np.random.default_rng(seed)
    layers = {c: _layer(c) for c in palette}
    for _ in range(n):
        x, y = where(rng) if where else (rng.uniform(-60, W + 60), rng.uniform(-60, H + 60))
        r = rng.uniform(rmin, rmax)
        a = int(rng.uniform(*alpha) * (1.0 if _clear(x, y) else 0.4))
        c = palette[int(rng.integers(len(palette)))]
        layers[c][1].ellipse((x - r, y - r, x + r, y + r), fill=tuple(c) + (a,))
    for layer, _draw in layers.values():
        img = _composite(img, layer, blur=blur)
    return img


def _pine(draw: ImageDraw.ImageDraw, x: float, base: float, h: float, color) -> None:
    """A pine-tree silhouette: three stacked triangles on a short trunk."""
    draw.rectangle((x - h * 0.03, base - h * 0.1, x + h * 0.03, base), fill=color)
    for top, bottom, half in ((0.0, 0.45, 0.17), (0.22, 0.72, 0.24), (0.45, 0.95, 0.31)):
        draw.polygon([(x, base - h + top * h), (x - half * h, base - h + bottom * h),
                      (x + half * h, base - h + bottom * h)], fill=color)


def _hills(img: Image.Image, layers) -> Image.Image:
    """Back-to-front filled horizon lines: (base, wave parts, colour, blur)."""
    xs = np.linspace(0, W, 400)
    for base, parts, color, blur in layers:
        hill, draw = _layer(color)
        _fill_below(draw, _wave(xs, base, parts), tuple(color) + (255,))
        img = _composite(img, hill, blur=blur)
    return img


# --------------------------------------------------------------------------
# scenes 06-30: same rules -- calm, static, no text, no faces or characters,
# mid-dark, detail at the edges and the bottom
# --------------------------------------------------------------------------

def aurora() -> Image.Image:
    rgb = _gradient([(0.0, (8, 22, 40)), (0.6, (14, 38, 58)), (1.0, (18, 44, 60))])
    img = _to_image(rgb, seed=601).convert("RGBA")
    xs = np.linspace(-100, W + 100, 360)
    for color, base, amp, phase, alpha in [((90, 230, 170), 150, 60, 0.4, 70),
                                           ((80, 200, 210), 230, 50, 1.9, 55),
                                           ((170, 120, 230), 110, 40, 3.1, 40)]:
        band, draw = _layer(color)
        top = base + amp * np.sin(2 * np.pi * xs / 1400 + phase)
        pts = list(zip(xs.tolist(), top.tolist())) + list(zip(xs[::-1].tolist(), (top[::-1] + 120).tolist()))
        draw.polygon(pts, fill=tuple(color) + (alpha,))
        img = _composite(img, band, blur=38)
    img = _stars(img, 90, seed=6, y_max=820)
    img = _hills(img, [(900, [(26, 900, 0.5), (12, 330, 2.0)], (16, 34, 46), 1.5),
                       (975, [(20, 700, 2.7), (8, 260, 0.9)], (10, 24, 34), 1.2)])
    trees, draw = _layer((8, 18, 26))
    for x, h in [(60, 230), (130, 180), (190, 260), (1780, 220), (1850, 270), (1900, 190)]:
        _pine(draw, x, H, h, (8, 18, 26, 255))
    return _composite(img, trees, blur=1.0).convert("RGB")


def misty_mountains() -> Image.Image:
    rgb = _gradient([(0.0, (36, 46, 82)), (0.55, (70, 84, 118)), (1.0, (70, 84, 118))])
    _glow(rgb, (1500, 640), 380, (150, 150, 170), 0.25)
    img = _to_image(rgb, seed=701).convert("RGBA")
    xs = np.linspace(0, W, 480)
    for base, rough, color, seed in [(700, 9, (82, 96, 128), 71), (790, 10, (62, 76, 108), 72),
                                     (880, 11, (44, 56, 86), 73), (970, 12, (28, 38, 62), 74)]:
        ridge, draw = _layer(color)
        _fill_below(draw, _ridge(xs, base, rough, seed), tuple(color) + (255,))
        img = _composite(img, ridge, blur=1.2)
        mist, draw = _layer((190, 196, 214))
        draw.rectangle((0, base - 40, W, base + 50), fill=(190, 196, 214, 28))
        img = _composite(img, mist, blur=30)
    return img.convert("RGB")


def desert_dunes() -> Image.Image:
    rgb = _gradient([(0.0, (42, 30, 70)), (0.5, (96, 60, 86)), (0.72, (150, 96, 86)), (1.0, (150, 96, 86))])
    _glow(rgb, (380, 700), 200, (230, 170, 120), 0.35)
    img = _to_image(rgb, seed=801).convert("RGBA")
    return _hills(img, [(780, [(50, 1700, 0.2), (18, 600, 2.2)], (120, 78, 62), 2.0),
                        (860, [(60, 1300, 1.8), (14, 450, 0.4)], (98, 62, 52), 1.6),
                        (960, [(46, 1500, 3.6), (10, 380, 1.2)], (72, 46, 42), 1.2)]).convert("RGB")


def moonlit_lake() -> Image.Image:
    rgb = _gradient([(0.0, (12, 20, 52)), (0.62, (30, 44, 86)), (0.63, (18, 30, 62)), (1.0, (10, 18, 44))])
    _glow(rgb, (300, 200), 160, (130, 150, 210), 0.35)
    img = _to_image(rgb, seed=901).convert("RGBA")
    img = _stars(img, 70, seed=9, y_max=620)
    moon, draw = _layer((236, 236, 214))
    draw.ellipse((300 - 40, 200 - 40, 300 + 40, 200 + 40), fill=(236, 236, 214, 255))
    img = _composite(img, moon, blur=1.4)
    shore, draw = _layer((14, 24, 48))
    xs = np.linspace(0, W, 400)
    top = _wave(xs, 668, [(14, 800, 0.4), (8, 260, 2.2)])
    pts = list(zip(xs.tolist(), top.tolist())) + [(W, 682), (0, 682)]
    draw.polygon(pts, fill=(14, 24, 48, 255))
    img = _composite(img, shore, blur=1.2)
    glint, draw = _layer((200, 210, 240))                        # the moon's path on the water
    rng = np.random.default_rng(91)
    for y in np.arange(700, 1060, 9):
        half = 22 + (y - 700) * 0.16
        for _ in range(int(rng.integers(1, 4))):               # short broken glints, not rungs
            x = 300 + rng.uniform(-half, half)
            length = rng.uniform(10, 34)
            draw.line((x - length / 2, y, x + length / 2, y),
                      fill=(200, 210, 240, int(rng.uniform(40, 100))), width=3)
    return _composite(img, glint, blur=2.6).convert("RGB")


def pine_forest() -> Image.Image:
    rgb = _gradient([(0.0, (30, 40, 70)), (0.6, (70, 72, 100)), (1.0, (60, 64, 88))])
    _glow(rgb, (960, 760), 520, (140, 120, 140), 0.2)
    img = _to_image(rgb, seed=1001).convert("RGBA")
    rng = np.random.default_rng(10)
    for row, (color, base, hmin, hmax, n) in enumerate([((50, 62, 76), 900, 160, 260, 26),
                                                         ((34, 46, 58), 990, 220, 340, 20),
                                                         ((20, 30, 40), H + 10, 300, 460, 14)]):
        trees, draw = _layer(color)
        for _ in range(n):
            x = rng.uniform(-40, W + 40)
            if 1230 < x < 1690 and row == 2:                    # the face column stays open
                continue
            _pine(draw, x, base, rng.uniform(hmin, hmax), tuple(color) + (255,))
        img = _composite(img, trees, blur=1.6 - row * 0.4)
        fog, draw = _layer((170, 176, 196))
        draw.rectangle((0, base - 120, W, base), fill=(170, 176, 196, 20))
        img = _composite(img, fog, blur=40)
    return img.convert("RGB")


def snowy_hills() -> Image.Image:
    rgb = _gradient([(0.0, (30, 44, 86)), (0.6, (66, 86, 128)), (1.0, (66, 86, 128))])
    img = _to_image(rgb, seed=1101).convert("RGBA")
    img = _hills(img, [(760, [(36, 1400, 0.6), (14, 520, 2.4)], (110, 126, 160), 2.0),
                       (850, [(40, 1100, 2.2), (12, 400, 0.8)], (92, 108, 144), 1.6),
                       (950, [(30, 1300, 4.0), (10, 350, 1.5)], (76, 92, 128), 1.2)])
    return _stars(img, 90, seed=11, size=(1.5, 3.4), alpha=(60, 130), color=(236, 240, 255),
                  blur=1.4).convert("RGB")


def sunset_sea() -> Image.Image:
    rgb = _gradient([(0.0, (36, 32, 76)), (0.45, (98, 64, 104)), (0.64, (168, 104, 104)),
                     (0.65, (40, 46, 82)), (1.0, (22, 28, 58))])
    _glow(rgb, (520, 700), 170, (240, 170, 130), 0.45)
    img = _to_image(rgb, seed=1201).convert("RGBA")
    sun, draw = _layer((246, 196, 150))
    draw.pieslice((520 - 90, 700 - 90, 520 + 90, 700 + 90), 180, 360, fill=(246, 196, 150, 230))
    img = _composite(img, sun, blur=3)
    waves, draw = _layer((200, 150, 150))
    rng = np.random.default_rng(12)
    for y in np.arange(722, 1070, 18):
        for _ in range(4):
            x = rng.uniform(0, W)
            if not _clear(x, y, margin=20):
                continue
            length = rng.uniform(60, 180)
            draw.line((x, y, x + length, y), fill=(200, 150, 150, int(rng.uniform(25, 60))), width=2)
    return _composite(img, waves, blur=1.5).convert("RGB")


def lavender_field() -> Image.Image:
    rgb = _gradient([(0.0, (44, 40, 92)), (0.55, (104, 84, 136)), (1.0, (104, 84, 136))])
    _glow(rgb, (1700, 640), 300, (220, 170, 170), 0.25)
    img = _to_image(rgb, seed=1301).convert("RGBA")
    img = _hills(img, [(700, [(16, 1200, 0.5)], (70, 62, 104), 2.0)])
    field, draw = _layer((96, 66, 138))
    vanish = (960, 640)
    for k in range(-14, 15):                                     # rows converging to the horizon
        x_bottom = 960 + k * 150
        draw.polygon([(vanish[0] + k * 6, 700), (vanish[0] + k * 6 + 4, 700),
                      (x_bottom + 46, H), (x_bottom - 46, H)], fill=(96, 66, 138, 150))
    img = _composite(img, field, blur=3)
    tops, draw = _layer((150, 110, 196))
    rng = np.random.default_rng(13)
    for _ in range(900):
        y = rng.uniform(760, H)
        x = rng.uniform(0, W)
        if not _clear(x, y, margin=10):
            continue
        r = 1.5 + (y - 700) / 140
        draw.ellipse((x - r, y - r * 1.8, x + r, y + r * 1.8), fill=(150, 110, 196, 110))
    return _composite(img, tops, blur=1.2).convert("RGB")


def coral_garden() -> Image.Image:
    rgb = _gradient([(0.0, (20, 86, 124)), (0.55, (16, 62, 104)), (1.0, (10, 38, 74))])
    img = _to_image(rgb, seed=1401).convert("RGBA")
    rays, draw = _layer((200, 236, 255))
    for x_top in (200, 700, 1180):
        draw.polygon([(x_top - 40, 0), (x_top + 40, 0), (x_top + 520, H), (x_top + 300, H)],
                     fill=(200, 236, 255, 18))
    img = _composite(img, rays, blur=50)
    rng = np.random.default_rng(14)
    for color, xs_range in [((150, 86, 120), (0, 380)), ((92, 120, 150), (1680, W)), ((170, 110, 96), (420, 900))]:
        coral, draw = _layer(color)
        for _ in range(5):
            x0, y0 = rng.uniform(*xs_range), H + 10
            for _branch in range(7):                            # a fan of soft branches
                angle = rng.uniform(-1.1, 1.1) - np.pi / 2
                length = rng.uniform(80, 210)
                x1, y1 = x0 + length * np.cos(angle), y0 + length * np.sin(angle)
                draw.line((x0, y0, x1, y1), fill=tuple(color) + (160,), width=int(rng.uniform(10, 18)))
                draw.ellipse((x1 - 12, y1 - 12, x1 + 12, y1 + 12), fill=tuple(color) + (160,))
        img = _composite(img, coral, blur=2.5)
    sand, draw = _layer((130, 118, 92))
    _fill_below(draw, _wave(np.linspace(0, W, 300), 1050, [(8, 520, 0.6)]), (130, 118, 92, 200))
    return _composite(img, sand, blur=4).convert("RGB")


def paper_lanterns() -> Image.Image:
    rgb = _gradient([(0.0, (14, 18, 50)), (1.0, (30, 34, 76))])
    img = _to_image(rgb, seed=1501).convert("RGBA")
    img = _stars(img, 50, seed=15, alpha=(70, 150))
    rng = np.random.default_rng(15)
    glow, gdraw = _layer((255, 176, 96))
    body, bdraw = _layer((236, 150, 86))
    placed = 0
    while placed < 16:
        x, y = rng.uniform(40, W - 40), rng.uniform(60, H - 60)
        s = rng.uniform(0.5, 1.2)
        if not _clear(x, y, margin=70 * s):
            continue
        gdraw.ellipse((x - 70 * s, y - 70 * s, x + 70 * s, y + 70 * s), fill=(255, 176, 96, 46))
        bdraw.rounded_rectangle((x - 22 * s, y - 30 * s, x + 22 * s, y + 30 * s), radius=10 * s,
                                fill=(236, 150, 86, 210))
        placed += 1
    img = _composite(img, glow, blur=24)
    return _composite(img, body, blur=1.5).convert("RGB")


def meadow_fireflies() -> Image.Image:
    rgb = _gradient([(0.0, (12, 24, 40)), (0.7, (20, 44, 52)), (1.0, (14, 34, 36))])
    img = _to_image(rgb, seed=1601).convert("RGBA")
    img = _hills(img, [(860, [(20, 1300, 0.4), (8, 400, 1.7)], (18, 40, 38), 1.5)])
    grass, draw = _layer((12, 30, 28))
    rng = np.random.default_rng(16)
    for x in np.arange(0, W, 9):
        h = rng.uniform(40, 150)
        lean = rng.uniform(-18, 18)
        draw.line((x, H, x + lean, H - h), fill=(12, 30, 28, 255), width=4)
    img = _composite(img, grass, blur=1.0)
    flies, draw = _layer((220, 240, 140))
    halo, hdraw = _layer((200, 230, 120))
    placed = 0
    while placed < 40:
        x, y = rng.uniform(0, W), rng.uniform(520, H - 30)
        if not _clear(x, y, margin=40):
            continue
        draw.ellipse((x - 2.5, y - 2.5, x + 2.5, y + 2.5), fill=(230, 250, 160, 230))
        hdraw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=(200, 230, 120, 40))
        placed += 1
    img = _composite(img, halo, blur=10)
    return _composite(img, flies, blur=0.8).convert("RGB")


def rain_bokeh() -> Image.Image:
    rgb = _gradient([(0.0, (18, 22, 46)), (1.0, (30, 30, 58))])
    img = _to_image(rgb, seed=1701).convert("RGBA")
    img = _blobs(img, [(255, 190, 120), (140, 180, 255), (220, 140, 200), (255, 230, 170)],
                 40, seed=17, rmin=30, rmax=110, alpha=(20, 46), blur=14)
    streaks, draw = _layer((200, 210, 240))                      # a few soft raindrop trails
    rng = np.random.default_rng(17)
    for _ in range(26):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        if not _clear(x, y, margin=40):
            continue
        draw.line((x, y, x + 6, y + rng.uniform(60, 140)), fill=(200, 210, 240, 40), width=3)
    return _composite(img, streaks, blur=2).convert("RGB")


def dusk_clouds() -> Image.Image:
    rgb = _gradient([(0.0, (36, 36, 86)), (0.6, (88, 70, 120)), (1.0, (120, 86, 124))])
    img = _to_image(rgb, seed=1801).convert("RGBA")

    def low(rng):
        return rng.uniform(-80, W + 80), rng.choice([rng.uniform(820, H + 60), rng.uniform(-60, 260)])
    img = _blobs(img, [(236, 186, 210), (196, 170, 230), (250, 206, 196)], 60, seed=18,
                 rmin=60, rmax=190, alpha=(20, 44), blur=30, where=low)
    return img.convert("RGB")


def nebula() -> Image.Image:
    rgb = _gradient([(0.0, (8, 10, 30)), (1.0, (14, 14, 40))])
    img = _to_image(rgb, seed=1901).convert("RGBA")
    img = _blobs(img, [(150, 90, 210), (70, 170, 200), (210, 100, 160)], 50, seed=19,
                 rmin=80, rmax=260, alpha=(12, 30), blur=60)
    img = _stars(img, 160, seed=19, size=(0.6, 1.8))
    return _stars(img, 12, seed=191, size=(2.2, 3.2), alpha=(160, 230), blur=1.6).convert("RGB")


def city_lights() -> Image.Image:
    rgb = _gradient([(0.0, (14, 18, 48)), (0.7, (40, 40, 84)), (1.0, (60, 50, 90))])
    _glow(rgb, (960, 1000), 520, (120, 96, 130), 0.3)
    img = _to_image(rgb, seed=2001).convert("RGBA")
    img = _stars(img, 40, seed=20, y_max=600, alpha=(60, 140))
    rng = np.random.default_rng(20)
    city, draw = _layer((14, 16, 32))
    windows, wdraw = _layer((255, 214, 150))
    x = 0.0
    while x < W:
        w = rng.uniform(50, 130)
        h = rng.uniform(80, 260) if not (1230 < x < 1700) else rng.uniform(60, 120)
        top = H - h
        draw.rectangle((x, top, x + w, H), fill=(14, 16, 32, 255))
        for wy in np.arange(top + 14, H - 10, 22):
            for wx in np.arange(x + 10, x + w - 10, 18):
                if rng.random() < 0.28:
                    wdraw.rectangle((wx, wy, wx + 6, wy + 8), fill=(255, 214, 150, int(rng.uniform(110, 200))))
        x += w + rng.uniform(4, 20)
    img = _composite(img, city, blur=0.8)
    return _composite(img, windows, blur=0.6).convert("RGB")


def autumn_leaves() -> Image.Image:
    rgb = _gradient([(0.0, (48, 26, 40)), (1.0, (70, 38, 36))])
    _glow(rgb, (1500, 220), 420, (110, 60, 50), 0.3)
    img = _to_image(rgb, seed=2101).convert("RGBA")
    rng = np.random.default_rng(21)
    for color in [(214, 112, 50), (190, 70, 46), (226, 168, 70)]:
        leaves, draw = _layer(color)
        placed = 0
        while placed < 18:
            x, y = rng.uniform(0, W), rng.uniform(0, H)
            s = rng.uniform(14, 34)
            if not _clear(x, y, margin=s + 30):
                continue
            a = rng.uniform(0, np.pi)
            dx, dy = np.cos(a) * s, np.sin(a) * s
            nx, ny = -dy * 0.45, dx * 0.45
            draw.polygon([(x - dx, y - dy), (x + nx, y + ny), (x + dx, y + dy), (x - nx, y - ny)],
                         fill=tuple(color) + (int(rng.uniform(120, 200)),))
            placed += 1
        img = _composite(img, leaves, blur=1.8)
    return img.convert("RGB")


def cherry_blossoms() -> Image.Image:
    rgb = _gradient([(0.0, (40, 40, 92)), (1.0, (80, 66, 116))])
    img = _to_image(rgb, seed=2201).convert("RGBA")
    branch, draw = _layer((28, 20, 34))
    pts = [(0, 140), (180, 170), (340, 150), (520, 200), (700, 180)]
    draw.line(pts, fill=(28, 20, 34, 255), width=16, joint="curve")
    for (x0, y0), (x1, y1) in [((180, 170), (260, 280)), ((340, 150), (420, 60)), ((520, 200), (600, 320))]:
        draw.line((x0, y0, x1, y1), fill=(28, 20, 34, 255), width=9)
    img = _composite(img, branch, blur=1.0)
    rng = np.random.default_rng(22)
    blossoms, bdraw = _layer((244, 186, 210))
    for cx, cy in [(180, 170), (260, 280), (340, 150), (420, 60), (520, 200), (600, 320), (700, 180)]:
        for _ in range(14):
            x, y = cx + rng.normal(0, 34), cy + rng.normal(0, 26)
            r = rng.uniform(6, 13)
            bdraw.ellipse((x - r, y - r, x + r, y + r), fill=(244, 186, 210, int(rng.uniform(150, 220))))
    img = _composite(img, blossoms, blur=1.2)
    petals, pdraw = _layer((244, 196, 216))
    placed = 0
    while placed < 30:
        x, y = rng.uniform(0, W), rng.uniform(250, H)
        if not _clear(x, y, margin=30):
            continue
        pdraw.ellipse((x - 5, y - 3, x + 5, y + 3), fill=(244, 196, 216, 120))
        placed += 1
    return _composite(img, petals, blur=1.0).convert("RGB")


def bamboo_grove() -> Image.Image:
    rgb = _gradient([(0.0, (22, 52, 54)), (1.0, (30, 66, 58))])
    _glow(rgb, (900, 300), 500, (90, 130, 110), 0.25)
    img = _to_image(rgb, seed=2301).convert("RGBA")
    rng = np.random.default_rng(23)
    for depth, (color, width, xs) in enumerate([((44, 86, 70), 26, [330, 420, 1180, 1228]),
                                                 ((30, 66, 52), 40, [40, 150, 270, 1720, 1830]),
                                                 ((18, 44, 36), 58, [90, 1890])]):
        stalks, draw = _layer(color)
        for x in xs:
            draw.rectangle((x - width / 2, -10, x + width / 2, H + 10), fill=tuple(color) + (255,))
            for y in np.arange(rng.uniform(40, 140), H, rng.uniform(150, 210)):    # the joints
                draw.rectangle((x - width / 2 - 3, y, x + width / 2 + 3, y + 6),
                               fill=tuple(int(c * 0.75) for c in color) + (255,))
            for _ in range(3):                                   # a few leaves
                y = rng.uniform(80, H - 80)
                side = rng.choice([-1, 1])
                draw.polygon([(x, y), (x + side * 130, y - 40), (x + side * 150, y - 30)],
                             fill=tuple(color) + (230,))
        img = _composite(img, stalks, blur=2.4 - depth * 0.8)
        mist, draw = _layer((170, 200, 186))
        draw.rectangle((0, 0, W, H), fill=(170, 200, 186, 10))
        img = _composite(img, mist)
    return img.convert("RGB")


def abstract_waves() -> Image.Image:
    rgb = _gradient([(0.0, (26, 28, 74)), (1.0, (40, 30, 86))])
    img = _to_image(rgb, seed=2401).convert("RGBA")
    xs = np.linspace(0, W, 400)
    for k, color in enumerate([(90, 120, 210), (150, 100, 200), (80, 170, 200), (120, 90, 180)]):
        band, draw = _layer(color)
        top = _wave(xs, 760 + k * 60, [(60, 1500 - k * 120, k * 1.3), (22, 520, k * 2.1)])
        pts = list(zip(xs.tolist(), top.tolist())) + list(zip(xs[::-1].tolist(), (top[::-1] + 90).tolist()))
        draw.polygon(pts, fill=tuple(color) + (60,))
        img = _composite(img, band, blur=10)
    return img.convert("RGB")


def low_poly_hills() -> Image.Image:
    rgb = _gradient([(0.0, (40, 46, 96)), (0.6, (96, 84, 130)), (1.0, (96, 84, 130))])
    _glow(rgb, (1560, 600), 260, (220, 170, 150), 0.3)
    img = _to_image(rgb, seed=2501).convert("RGBA")
    rng = np.random.default_rng(25)
    for base, color in [(760, (70, 92, 104)), (860, (50, 74, 84)), (960, (34, 56, 64))]:
        hill, draw = _layer(color)
        xs = np.linspace(-60, W + 60, 18)
        ys = base + rng.uniform(-60, 40, xs.size)
        for i in range(xs.size - 1):                           # flat-shaded facets
            shade = rng.uniform(0.85, 1.15)
            c = tuple(int(min(255, v * shade)) for v in color)
            mid = (xs[i] + xs[i + 1]) / 2
            draw.polygon([(xs[i], ys[i]), (xs[i + 1], ys[i + 1]), (mid, H)], fill=c + (255,))
            draw.polygon([(xs[i], ys[i]), (mid, H), (xs[i], H)], fill=tuple(int(v * 0.92) for v in c) + (255,))
            draw.polygon([(xs[i + 1], ys[i + 1]), (xs[i + 1], H), (mid, H)], fill=tuple(int(v * 0.88) for v in c) + (255,))
        img = _composite(img, hill)
    return img.convert("RGB")


def watercolour_wash() -> Image.Image:
    rgb = _gradient([(0.0, (46, 52, 84)), (1.0, (56, 46, 78))])
    img = _to_image(rgb, seed=2601).convert("RGBA")
    img = _blobs(img, [(120, 150, 170), (150, 110, 150), (100, 130, 140), (170, 130, 120)],
                 34, seed=26, rmin=120, rmax=320, alpha=(18, 36), blur=50)
    paper = np.random.default_rng(26).normal(0, 1.6, (H, W, 1))   # a faint paper grain
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) + paper
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def planets() -> Image.Image:
    rgb = _gradient([(0.0, (8, 10, 30)), (1.0, (18, 16, 46))])
    img = _to_image(rgb, seed=2701).convert("RGBA")
    img = _stars(img, 140, seed=27)
    for (cx, cy, r, color, ring) in [(180, 900, 230, (96, 120, 180), False),
                                     (330, 170, 70, (190, 140, 110), True),
                                     (1820, 960, 120, (140, 100, 160), False)]:
        body, draw = _layer(color)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(color) + (255,))
        img = _composite(img, body, blur=1.2)
        shade, draw = _layer((6, 8, 24))                       # a soft night side
        draw.ellipse((cx - r * 0.55, cy - r * 1.05, cx + r * 1.5, cy + r * 1.05), fill=(6, 8, 24, 150))
        img = _composite(img, shade, blur=r * 0.25)
        if ring:
            rings, draw = _layer((220, 200, 170))
            draw.ellipse((cx - r * 1.8, cy - r * 0.45, cx + r * 1.8, cy + r * 0.45),
                         outline=(220, 200, 170, 140), width=max(3, int(r * 0.08)))
            img = _composite(img, rings, blur=1.0)
    return img.convert("RGB")


def arctic_ice() -> Image.Image:
    rgb = _gradient([(0.0, (16, 30, 60)), (0.62, (44, 70, 104)), (0.63, (16, 34, 58)), (1.0, (10, 24, 44))])
    img = _to_image(rgb, seed=2801).convert("RGBA")
    band, draw = _layer((110, 220, 200))                         # a faint aurora
    xs = np.linspace(0, W, 300)
    top = _wave(xs, 140, [(40, 1200, 0.7)])
    draw.polygon(list(zip(xs.tolist(), top.tolist())) + list(zip(xs[::-1].tolist(), (top[::-1] + 90).tolist())),
                 fill=(110, 220, 200, 40))
    img = _composite(img, band, blur=40)
    img = _stars(img, 60, seed=28, y_max=600)
    bergs, draw = _layer((130, 160, 190))
    for x0, w, h in [(40, 300, 120), (1700, 220, 90), (900, 160, 40)]:
        draw.polygon([(x0, 682), (x0 + w * 0.3, 682 - h), (x0 + w * 0.55, 682 - h * 0.7),
                      (x0 + w * 0.75, 682 - h * 0.9), (x0 + w, 682)], fill=(130, 160, 190, 255))
    img = _composite(img, bergs, blur=1.2)
    floes, draw = _layer((90, 120, 150))
    rng = np.random.default_rng(28)
    placed = 0
    while placed < 22:
        x, y = rng.uniform(0, W), rng.uniform(720, H - 10)
        if not _clear(x, y, margin=40):
            continue
        w, h = rng.uniform(70, 200) * (y / 900), rng.uniform(5, 13) * (y / 900)
        draw.ellipse((x - w, y - h, x + w, y + h), fill=(96, 126, 156, int(rng.uniform(110, 160))))
        placed += 1
    return _composite(img, floes, blur=1.5).convert("RGB")


def savanna_dusk() -> Image.Image:
    rgb = _gradient([(0.0, (44, 32, 74)), (0.55, (130, 76, 84)), (0.75, (178, 110, 80)), (1.0, (178, 110, 80))])
    _glow(rgb, (1500, 760), 220, (240, 180, 120), 0.4)
    img = _to_image(rgb, seed=2901).convert("RGBA")
    img = _hills(img, [(860, [(10, 1500, 0.3), (5, 500, 1.4)], (60, 36, 38), 1.0)])
    trees, draw = _layer((30, 18, 24))
    ink = (30, 18, 24, 255)
    for x, s in [(190, 1.0), (430, 0.6), (1830, 0.8)]:
        fork = (x + 6 * s, 880 - 110 * s)
        draw.line((x, 880, *fork), fill=ink, width=int(14 * s))
        for dx in (-70, 10, 85):                                 # the trunk forks into branches
            draw.line((*fork, x + dx * s, 880 - 185 * s), fill=ink, width=int(8 * s))
        for cx, cy, rx, ry in [(-80, -195, 95, 20), (20, -210, 120, 24), (110, -192, 90, 19), (15, -230, 70, 16)]:
            draw.ellipse((x + (cx - rx) * s, 880 + (cy - ry) * s, x + (cx + rx) * s, 880 + (cy + ry) * s), fill=ink)
    img = _composite(img, trees, blur=1.0)
    grass, draw = _layer((44, 26, 30))
    _fill_below(draw, _wave(np.linspace(0, W, 300), 900, [(6, 260, 0.2), (3, 90, 1.7)]), (44, 26, 30, 255))
    return _composite(img, grass, blur=0.8).convert("RGB")


def hot_air_balloons() -> Image.Image:
    rgb = _gradient([(0.0, (44, 52, 104)), (1.0, (100, 96, 140))])
    img = _to_image(rgb, seed=3001).convert("RGBA")

    def low(rng):
        return rng.uniform(-80, W + 80), rng.uniform(880, H + 80)
    img = _blobs(img, [(220, 210, 236), (200, 196, 230)], 30, seed=30, rmin=70, rmax=160,
                 alpha=(24, 44), blur=26, where=low)
    for x, y, s, color in [(200, 260, 1.0, (214, 110, 96)), (430, 160, 0.6, (110, 160, 200)),
                           (120, 640, 0.7, (226, 178, 90)), (1820, 200, 0.8, (150, 120, 196))]:
        balloon, draw = _layer(color)
        draw.ellipse((x - 70 * s, y - 85 * s, x + 70 * s, y + 70 * s), fill=tuple(color) + (235,))
        draw.polygon([(x - 46 * s, y + 46 * s), (x + 46 * s, y + 46 * s), (x + 16 * s, y + 110 * s),
                      (x - 16 * s, y + 110 * s)], fill=tuple(color) + (235,))
        img = _composite(img, balloon, blur=1.2)
        basket, draw = _layer((70, 50, 44))
        draw.rectangle((x - 14 * s, y + 118 * s, x + 14 * s, y + 140 * s), fill=(70, 50, 44, 240))
        draw.line((x - 14 * s, y + 110 * s, x - 12 * s, y + 118 * s), fill=(70, 50, 44, 240), width=2)
        draw.line((x + 14 * s, y + 110 * s, x + 12 * s, y + 118 * s), fill=(70, 50, 44, 240), width=2)
        img = _composite(img, basket, blur=0.8)
    return img.convert("RGB")



SCENES = {
    "01-starry-night.jpg": starry_night,
    "02-under-the-sea.jpg": under_the_sea,
    "03-rolling-hills.jpg": rolling_hills,
    "04-soft-bubbles.jpg": soft_bubbles,
    "05-classic-purple.jpg": classic_purple,
    "06-aurora.jpg": aurora,
    "07-misty-mountains.jpg": misty_mountains,
    "08-desert-dunes.jpg": desert_dunes,
    "09-moonlit-lake.jpg": moonlit_lake,
    "10-pine-forest.jpg": pine_forest,
    "11-snowy-hills.jpg": snowy_hills,
    "12-sunset-sea.jpg": sunset_sea,
    "13-lavender-field.jpg": lavender_field,
    "14-coral-garden.jpg": coral_garden,
    "15-paper-lanterns.jpg": paper_lanterns,
    "16-meadow-fireflies.jpg": meadow_fireflies,
    "17-rain-bokeh.jpg": rain_bokeh,
    "18-dusk-clouds.jpg": dusk_clouds,
    "19-nebula.jpg": nebula,
    "20-city-lights.jpg": city_lights,
    "21-autumn-leaves.jpg": autumn_leaves,
    "22-cherry-blossoms.jpg": cherry_blossoms,
    "23-bamboo-grove.jpg": bamboo_grove,
    "24-abstract-waves.jpg": abstract_waves,
    "25-low-poly-hills.jpg": low_poly_hills,
    "26-watercolour-wash.jpg": watercolour_wash,
    "27-planets.jpg": planets,
    "28-arctic-ice.jpg": arctic_ice,
    "29-savanna-dusk.jpg": savanna_dusk,
    "30-hot-air-balloons.jpg": hot_air_balloons,
}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    out_dir = args[0] if args else backgrounds_dir()          # optional: a folder to preview into
    os.makedirs(out_dir, exist_ok=True)
    for name, scene in SCENES.items():
        img = scene()
        luma = mean_luminance(img)
        if luma > DEFAULT_MAX_LUMA:
            raise SystemExit(f"{name}: mean luma {luma:.2f} exceeds {DEFAULT_MAX_LUMA}")
        path = os.path.join(out_dir, name)
        img.save(path, "JPEG", quality=92, optimize=True, subsampling=0)
        print(f"{name:26s} luma {luma:.2f}  {os.path.getsize(path) / 1024:6.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
