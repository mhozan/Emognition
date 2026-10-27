# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for background-picture preparation (emognition.imaging; Pillow only)."""

import numpy as np
import pytest
from PIL import Image, ImageCms

from emognition.core.backgrounds import CALM_GRADIENT
from emognition.imaging import (
    DEFAULT_MAX_LUMA,
    PictureError,
    calm_gradient,
    cap_luminance,
    import_picture,
    load_cover,
    mean_luminance,
    render_background,
)
from emognition.imaging import backgrounds as imaging_backgrounds

_ORIENTATION, _MAKE = 0x0112, 0x010F


def _save(path, size=(400, 200), color=(200, 60, 60), fmt="JPEG", **kwargs):
    Image.new("RGB", size, color).save(path, fmt, **kwargs)
    return str(path)


# --- the default gradient ---------------------------------------------------

def test_gradient_has_exact_size_and_is_deterministic():
    a = calm_gradient((320, 180))
    assert a.size == (320, 180) and a.mode == "RGB"
    assert np.array_equal(np.asarray(a), np.asarray(calm_gradient((320, 180))))


def test_gradient_is_smooth_and_dark_enough_for_white_text():
    img = calm_gradient((1920, 1080))
    rows = np.asarray(img, dtype=np.float64).mean(axis=1)   # (h, 3) mean of each row
    assert np.abs(np.diff(rows, axis=0)).max() <= 1.0        # no visible banding steps
    assert mean_luminance(img) <= DEFAULT_MAX_LUMA


# --- brightness ---------------------------------------------------------------

def test_cap_luminance_dims_bright_pictures_only():
    white = Image.new("RGB", (50, 50), (255, 255, 255))
    capped = cap_luminance(white, 0.45)
    assert abs(mean_luminance(capped) - 0.45) < 0.01
    dark = Image.new("RGB", (50, 50), (20, 20, 20))
    assert cap_luminance(dark, 0.45) is dark
    assert cap_luminance(white, None) is white


# --- loading for display ------------------------------------------------------

def test_load_cover_fills_the_target_exactly(tmp_path):
    path = _save(tmp_path / "wide.jpg", size=(800, 200))
    img = load_cover(path, (300, 300))
    assert img.size == (300, 300) and img.mode == "RGB"


def test_load_cover_flattens_transparency_and_dims(tmp_path):
    rgba = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    rgba.paste((0, 0, 0, 0), (0, 0, 32, 64))                 # left half fully transparent
    rgba.save(tmp_path / "t.png")
    img = load_cover(str(tmp_path / "t.png"), (64, 64), max_luma=None)
    assert img.getpixel((5, 5)) == (0, 0, 0) and img.getpixel((60, 5)) == (255, 255, 255)


def test_render_background_never_raises(tmp_path):
    good, problem = render_background(CALM_GRADIENT, (64, 36))
    assert good.size == (64, 36) and problem is None
    (tmp_path / "broken.jpg").write_bytes(b"not a picture")
    fallback, problem = render_background(str(tmp_path / "broken.jpg"), (64, 36))
    assert fallback.size == (64, 36) and "calm gradient" in problem


# --- importing ("Add picture...") ---------------------------------------------

def test_import_applies_orientation_and_strips_metadata(tmp_path):
    exif = Image.Exif()
    exif[_ORIENTATION] = 6          # "rotate 90 degrees to display" (portrait phone photo)
    exif[_MAKE] = "SecretPhone"
    src = _save(tmp_path / "IMG 0042.JPG", size=(400, 200), exif=exif,
                icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    before = open(src, "rb").read()

    out = import_picture(src, str(tmp_path / "mine"))
    assert out.endswith("img-0042.jpg")
    with Image.open(out) as img:
        assert img.size == (200, 400)                     # now upright portrait
        assert len(img.getexif()) == 0                    # no EXIF at all (GPS included)
        assert "icc_profile" not in img.info
    assert open(src, "rb").read() == before               # original untouched


def test_import_fits_inside_the_box_but_never_enlarges(tmp_path):
    big = import_picture(_save(tmp_path / "big.png", size=(3000, 1000), fmt="PNG"), str(tmp_path / "o"))
    small = import_picture(_save(tmp_path / "small.png", size=(100, 80), fmt="PNG"), str(tmp_path / "o"))
    with Image.open(big) as b, Image.open(small) as s:
        assert b.size == (2560, 853) and s.size == (100, 80)


def test_import_never_overwrites(tmp_path):
    src = _save(tmp_path / "sky.jpg")
    first = import_picture(src, str(tmp_path / "o"))
    second = import_picture(src, str(tmp_path / "o"))
    assert first != second and second.endswith("sky-2.jpg")


def test_import_rejects_non_pictures_and_unsupported_formats(tmp_path):
    (tmp_path / "fake.jpg").write_text("hello")
    with pytest.raises(PictureError):
        import_picture(str(tmp_path / "fake.jpg"), str(tmp_path / "o"))
    tiff = _save(tmp_path / "scan.tif", fmt="TIFF")
    with pytest.raises(PictureError):
        import_picture(tiff, str(tmp_path / "o"))
    with pytest.raises(PictureError):
        import_picture(str(tmp_path / "missing.jpg"), str(tmp_path / "o"))


def test_import_rejects_oversized_pictures(tmp_path, monkeypatch):
    monkeypatch.setattr(imaging_backgrounds, "MAX_IMPORT_PIXELS", 1000)
    with pytest.raises(PictureError, match="too large"):
        import_picture(_save(tmp_path / "huge.jpg", size=(100, 100)), str(tmp_path / "o"))
