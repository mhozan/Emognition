# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Generate the bundled participant-window backgrounds into assets/backgrounds/.

Run with:  .venv/bin/python scripts/generate_backgrounds.py

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


SCENES = {
    "01-starry-night.jpg": starry_night,
    "02-under-the-sea.jpg": under_the_sea,
    "03-rolling-hills.jpg": rolling_hills,
    "04-soft-bubbles.jpg": soft_bubbles,
    "05-classic-purple.jpg": classic_purple,
}


def main() -> int:
    out_dir = backgrounds_dir()
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
