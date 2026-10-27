# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Preparing background pictures for the participant window (Pillow only).

Three jobs, all done *outside* the timing-critical trial loop:

* :func:`calm_gradient` renders the default background -- a soothing, text-free
  indigo-to-teal blend -- at exactly the window's pixel size. Generated rather
  than shipped as a file, so it is crisp on any screen and always available as
  the fallback when a picture can't be read.
* :func:`load_cover` decodes a picture and crops it to fill the window without
  distortion (CSS "cover"), dimming it if it is too bright for the white text.
* :func:`import_picture` turns an experimenter's photo into a clean, modest JPEG
  in their personal backgrounds folder: right way up, sRGB, no metadata (phone
  photos carry GPS location), no larger than needed. The expensive decode happens
  once here, never in front of a participant.

The original program did all of this implicitly with ``imread`` at the moment it
switched pictures (bgchanger.m), inside the response callback. Here the
experiment only ever receives ready-to-upload images.
"""

from __future__ import annotations

import io
import os
import re
import warnings

import numpy as np
from PIL import Image, ImageCms, ImageEnhance, ImageOps, ImageStat, UnidentifiedImageError

from ..core.backgrounds import CALM_GRADIENT

# Pictures brighter than this (mean luma, 0..1) are dimmed down to it, so the
# white prompt and key numbers stay readable on any photo.
DEFAULT_MAX_LUMA = 0.45

# What "Add picture..." accepts. Restricting the decoders keeps exotic formats
# (and their parsers) out of reach of an arbitrary file.
IMPORT_FORMATS: tuple[str, ...] = ("JPEG", "PNG", "WEBP", "BMP", "GIF")
# Refuse anything over 64 megapixels before decoding it (decompression bombs and
# needless memory spikes); Pillow's own guard only kicks in above ~89 MP.
MAX_IMPORT_PIXELS = 64_000_000
# Imported pictures are fitted inside this box -- plenty for a calm background
# on a 1440p or Retina screen, and quick to decode at session start.
IMPORT_BOX: tuple[int, int] = (2560, 1600)

# The default gradient: deep indigo-blue at the top easing into muted teal.
_GRADIENT_TOP = (30, 42, 92)
_GRADIENT_BOTTOM = (36, 104, 112)
# A faint, wide glow (x, y as fractions of width/height; radius as a fraction of
# height; brightness gain in 0..255 levels) so the screen doesn't look flat.
_GRADIENT_GLOW = (0.30, 0.38, 0.55, 16.0)

# EXIF orientations 5-8 rotate by 90 degrees, i.e. stored width/height are swapped.
_EXIF_ORIENTATION = 0x0112
_ROTATED_ORIENTATIONS = frozenset({5, 6, 7, 8})

_SRGB = ImageCms.createProfile("sRGB")


class PictureError(ValueError):
    """A picture couldn't be imported; the message is meant for the experimenter."""


# --------------------------------------------------------------------------
# the default background
# --------------------------------------------------------------------------

def calm_gradient(size: tuple[int, int], *, seed: int = 0) -> Image.Image:
    """Render the default background: a soft vertical blend with a gentle glow.

    A smoothstep easing keeps both ends calm, and +/-1-level triangular dither
    hides the 8-bit steps that would otherwise show as bands on a large screen.
    The same *seed* always gives the same pixels.
    """
    width, height = max(1, int(size[0])), max(1, int(size[1]))
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]      # (h, 1)
    ease = y * y * (3.0 - 2.0 * y)
    top = np.asarray(_GRADIENT_TOP, dtype=np.float32)
    bottom = np.asarray(_GRADIENT_BOTTOM, dtype=np.float32)
    rgb = np.broadcast_to(top + (bottom - top) * ease[..., None], (height, width, 3)).copy()

    # Glow, in height-normalised coordinates so it stays round on any aspect ratio.
    gx, gy, radius, gain = _GRADIENT_GLOW
    aspect = width / height
    x = np.linspace(0.0, aspect, width, dtype=np.float32)[None, :]  # (1, w)
    dist2 = (x - gx * aspect) ** 2 + (y - gy) ** 2
    rgb += (gain * np.exp(-dist2 / (2.0 * radius * radius)))[..., None]

    # Triangular dither shared by the three channels (no colour speckle).
    rng = np.random.default_rng(seed)
    rgb += (rng.random((height, width, 1), dtype=np.float32)
            - rng.random((height, width, 1), dtype=np.float32))
    return Image.fromarray(np.clip(np.rint(rgb), 0, 255).astype(np.uint8))


# --------------------------------------------------------------------------
# brightness
# --------------------------------------------------------------------------

def mean_luminance(image: Image.Image) -> float:
    """Mean luma of *image* in 0..1 (Pillow's ITU-R 601 'L' conversion)."""
    return ImageStat.Stat(image.convert("L")).mean[0] / 255.0


def cap_luminance(image: Image.Image, max_luma: float | None) -> Image.Image:
    """Darken *image* uniformly so its mean luma is at most *max_luma*.

    Pictures already dark enough are returned untouched (the bundled ones are
    designed below the cap); ``max_luma=None`` disables the cap.
    """
    if max_luma is None:
        return image
    mean = mean_luminance(image)
    if mean <= max_luma or mean <= 0.0:
        return image
    return ImageEnhance.Brightness(image).enhance(max_luma / mean)


# --------------------------------------------------------------------------
# decoding helpers
# --------------------------------------------------------------------------

def _orientation(image: Image.Image) -> int:
    try:
        return int(image.getexif().get(_EXIF_ORIENTATION, 1))
    except Exception:  # noqa: BLE001 -- unreadable EXIF just means "upright"
        return 1


def _draft(image: Image.Image, display_size: tuple[int, int]) -> None:
    """Let the JPEG decoder skip detail we will throw away (big speed-up).

    Must run before :func:`ImageOps.exif_transpose`, which loads the pixels. The
    decoder works in *stored* orientation, so the size is swapped for pictures
    that EXIF says to rotate by 90 degrees.
    """
    w, h = display_size
    if _orientation(image) in _ROTATED_ORIENTATIONS:
        w, h = h, w
    image.draft("RGB", (max(1, w), max(1, h)))


def _displayed_size(image: Image.Image) -> tuple[int, int]:
    w, h = image.size
    return (h, w) if _orientation(image) in _ROTATED_ORIENTATIONS else (w, h)


def _to_srgb_rgb(image: Image.Image) -> Image.Image:
    """Convert to plain sRGB RGB: honour an embedded ICC profile, flatten alpha.

    Phones save in Display-P3 and some cameras in AdobeRGB; ignoring the profile
    would show those colours washed out or oversaturated. Transparent areas are
    composited over black so they read as "no picture" rather than garbage.
    """
    if image.mode == "P":
        image = image.convert("RGBA" if "transparency" in image.info else "RGB")
    elif image.mode == "LA":
        image = image.convert("RGBA")
    elif image.mode not in ("RGB", "RGBA", "L", "CMYK"):
        image = image.convert("RGB")

    icc = image.info.get("icc_profile")
    if icc:
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            out_mode = "RGBA" if image.mode == "RGBA" else "RGB"
            image = ImageCms.profileToProfile(image, src, _SRGB, outputMode=out_mode)
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass  # unusual/broken profile: treat the pixels as sRGB

    if image.mode == "RGBA":
        backdrop = Image.new("RGBA", image.size, (0, 0, 0, 255))
        image = Image.alpha_composite(backdrop, image)
    return image.convert("RGB")


# --------------------------------------------------------------------------
# loading for display
# --------------------------------------------------------------------------

def load_cover(
    path: str,
    size: tuple[int, int],
    *,
    max_luma: float | None = DEFAULT_MAX_LUMA,
) -> Image.Image:
    """Decode *path* and crop/scale it to fill exactly *size* pixels (no distortion).

    Raises whatever Pillow raises for unreadable files; callers that must never
    fail (the experiment) use :func:`render_background` instead.
    """
    target = (max(1, int(size[0])), max(1, int(size[1])))
    with Image.open(path) as image:
        _draft(image, target)
        image = ImageOps.exif_transpose(image)
        image = _to_srgb_rgb(image)
    fitted = ImageOps.fit(image, target, method=Image.Resampling.LANCZOS)
    return cap_luminance(fitted, max_luma)


def render_background(
    source: str,
    size: tuple[int, int],
    *,
    max_luma: float | None = DEFAULT_MAX_LUMA,
) -> tuple[Image.Image, str | None]:
    """Image for a background *source*, never raising.

    Returns ``(image, problem)``: *problem* is ``None`` on success, or a one-line
    explanation when the picture couldn't be read and the calm gradient was used
    instead (the original showed a 2x2 black image and printed a hint).
    """
    if source == CALM_GRADIENT:
        return calm_gradient(size), None
    try:
        return load_cover(source, size, max_luma=max_luma), None
    except Exception as exc:  # noqa: BLE001 -- a bad picture must never stop a session
        return calm_gradient(size), (
            f"Could not load background picture {source!r} ({exc}); "
            "showing the calm gradient instead."
        )


# --------------------------------------------------------------------------
# importing an experimenter's picture ("Add picture...")
# --------------------------------------------------------------------------

def _fit_inside(size: tuple[int, int], box: tuple[int, int]) -> tuple[int, int]:
    """Largest size with *size*'s aspect ratio that fits in *box* (never enlarges)."""
    w, h = size
    scale = min(1.0, box[0] / w, box[1] / h)
    return max(1, round(w * scale)), max(1, round(h * scale))


def _slug(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")[:60].strip("-")
    return slug or "picture"


def _unique_path(folder: str, stem: str, ext: str) -> str:
    candidate = os.path.join(folder, stem + ext)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem}-{n}{ext}")
        n += 1
    return candidate


def import_picture(
    src: str,
    dst_dir: str,
    *,
    max_box: tuple[int, int] = IMPORT_BOX,
    quality: int = 90,
) -> str:
    """Copy *src* into *dst_dir* as a clean JPEG; return the new file's path.

    The copy is upright (EXIF orientation applied), sRGB, fitted inside *max_box*,
    and carries **no metadata** -- Pillow writes no EXIF/ICC unless asked to.
    The original file is never modified.

    Raises:
        PictureError: for missing, unsupported, damaged or oversized files.
    """
    name = os.path.basename(src)
    try:
        with warnings.catch_warnings():
            # Treat Pillow's "this might be a decompression bomb" warning as fatal.
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(src, formats=IMPORT_FORMATS)
    except FileNotFoundError as exc:
        raise PictureError(f"File not found: {src}") from exc
    except (UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning, OSError) as exc:
        raise PictureError(
            f"{name} is not a supported picture (use JPEG, PNG, WebP, BMP or GIF)."
        ) from exc

    with image:
        width, height = image.size
        if width * height > MAX_IMPORT_PIXELS:
            raise PictureError(
                f"{name} is too large ({width}x{height}); please use a picture under "
                f"{MAX_IMPORT_PIXELS // 1_000_000} megapixels."
            )
        target = _fit_inside(_displayed_size(image), max_box)
        try:
            _draft(image, target)
            picture = _to_srgb_rgb(ImageOps.exif_transpose(image))
        except (OSError, ValueError, SyntaxError) as exc:
            raise PictureError(f"{name} looks damaged and could not be read.") from exc

    picture.thumbnail(max_box, Image.Resampling.LANCZOS)  # fit inside; never enlarges
    os.makedirs(dst_dir, exist_ok=True)
    dest = _unique_path(dst_dir, _slug(src), ".jpg")
    picture.save(dest, "JPEG", quality=quality, optimize=True, subsampling=0)
    return dest
