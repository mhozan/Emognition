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

from emognition.core import Emotion
from emognition.ui.assets import Caption, audio_dir, emoticon_path


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
