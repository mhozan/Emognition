# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for stimulus filename parsing -- the ..._EMO_G.wav contract.

These run without a display or audio device (pure logic), so they're safe in CI.
We point them at the real bundled stimuli under assets/audio/ as a smoke test.
"""

import os

import pytest

from emognition.core import Emotion, Gender, parse_stimulus_filename, scan_audio_dir

ASSETS_AUDIO = os.path.join(
    os.path.dirname(__file__), os.pardir, "assets", "audio"
)


@pytest.mark.parametrize(
    "name, emotion, gender",
    [
        ("01_ang_f.wav", Emotion.ANGRY, Gender.FEMALE),
        ("02_hap_m.wav", Emotion.HAPPY, Gender.MALE),
        ("03_neu_f.wav", Emotion.NEUTRAL, Gender.FEMALE),
        ("04_sad_m.wav", Emotion.SAD, Gender.MALE),
        ("05_sca_f.wav", Emotion.SCARED, Gender.FEMALE),
        # case-insensitivity + free-form prefix (per the original tooltip)
        ("subjectA_recording12_HAP_M.wav", Emotion.HAPPY, Gender.MALE),
        ("weird-Name_ScA_f.wav", Emotion.SCARED, Gender.FEMALE),
    ],
)
def test_valid_names(name, emotion, gender):
    stim = parse_stimulus_filename(name)
    assert stim is not None
    assert stim.emotion is emotion
    assert stim.gender is gender


@pytest.mark.parametrize(
    "name",
    [
        "notes.txt",            # wrong extension
        "01_ang.wav",           # missing gender
        "01_xyz_f.wav",         # unknown emotion tag
        "happy.wav",            # no _EMO_G suffix
        "01_ang_x.wav",         # invalid gender letter
    ],
)
def test_invalid_names_are_skipped(name):
    assert parse_stimulus_filename(name) is None


def test_canonical_index_map():
    # The legacy report ordering must never drift: 1=Happy..5=Angry.
    assert int(Emotion.HAPPY) == 1
    assert int(Emotion.SCARED) == 2
    assert int(Emotion.NEUTRAL) == 3
    assert int(Emotion.SAD) == 4
    assert int(Emotion.ANGRY) == 5


def test_scan_bundled_assets():
    stimuli = scan_audio_dir(ASSETS_AUDIO)
    # The repo ships 10 reference clips (5 emotions x 2 genders).
    assert len(stimuli) == 10
    assert {s.emotion for s in stimuli} == set(Emotion)
    assert {s.gender for s in stimuli} == {Gender.FEMALE, Gender.MALE}
