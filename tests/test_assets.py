# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for asset-path resolution (pure logic, no display needed).

Note: importing emognition.ui.assets does NOT import PsychoPy -- assets.py only
touches the Emotion enum and the filesystem -- so this stays a fast, headless test.
"""

import os

import pytest
from PIL import Image

from emognition.core import Emotion
from emognition.core.backgrounds import list_pictures
from emognition.imaging import DEFAULT_MAX_LUMA, mean_luminance
from emognition.ui.assets import (
    Caption,
    audio_dir,
    background_folders,
    backgrounds_dir,
    emoticon_path,
    user_backgrounds_dir,
)

# Where the experiment draws text/buttons on a 1920x1080 frame (see
# scripts/generate_backgrounds.py): these areas must stay dark enough for white text.
_TEXT_REGIONS = [(1270, 90, 1650, 990), (470, 400, 1130, 580)]


@pytest.mark.parametrize("caption, prefix", [
    (Caption.ENGLISH, "0"),
    (Caption.MANDARIN, "1"),
    (Caption.NONE, "2"),
])
def test_emoticon_filenames_follow_prefix_convention(caption, prefix):
    path = emoticon_path(Emotion.HAPPY, caption)
    assert os.path.basename(path) == f"{prefix}happy.png"


@pytest.mark.parametrize("emotion", list(Emotion))
def test_every_emoticon_file_exists(emotion):
    # All five faces must exist in the default (no-caption) style.
    assert os.path.exists(emoticon_path(emotion, Caption.NONE))


def test_audio_dir_has_ten_reference_clips():
    wavs = [f for f in os.listdir(audio_dir()) if f.endswith(".wav")]
    assert len(wavs) == 10


def test_bundled_backgrounds_are_present():
    names = [os.path.basename(p) for p in list_pictures(backgrounds_dir())]
    assert names == [
        "01-starry-night.jpg", "02-under-the-sea.jpg", "03-rolling-hills.jpg",
        "04-soft-bubbles.jpg", "05-classic-purple.jpg",
    ]


@pytest.mark.parametrize("path", list_pictures(backgrounds_dir()))
def test_bundled_background_is_calm_enough_for_white_text(path):
    with Image.open(path) as img:
        assert img.size == (1920, 1080) and img.mode == "RGB"
        assert mean_luminance(img) <= DEFAULT_MAX_LUMA
        for box in _TEXT_REGIONS:
            assert mean_luminance(img.crop(box)) <= DEFAULT_MAX_LUMA


def test_background_folders_are_bundled_then_user():
    bundled, user = background_folders()
    assert bundled == backgrounds_dir()
    assert user == user_backgrounds_dir() and user.endswith(os.path.join(".emognition", "backgrounds"))
