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

from emognition.core import Emotion, Sex, parse_stimulus_filename, scan_audio_dir

ASSETS_AUDIO = os.path.join(
    os.path.dirname(__file__), os.pardir, "assets", "audio"
)


@pytest.mark.parametrize(
    "name, emotion, sex, recording_id",
    [
        ("01_ang_f.wav", Emotion.ANGRY, Sex.FEMALE, "01"),
        ("02_hap_m.wav", Emotion.HAPPY, Sex.MALE, "02"),
        ("03_neu_f.wav", Emotion.NEUTRAL, Sex.FEMALE, "03"),
        ("04_sad_m.wav", Emotion.SAD, Sex.MALE, "04"),
        ("05_sca_f.wav", Emotion.SCARED, Sex.FEMALE, "05"),
        # 'u' = unknown speaker sex
        ("clip07_neu_u.wav", Emotion.NEUTRAL, Sex.UNKNOWN, "clip07"),
        # case-insensitivity + free-form prefix kept as recording_id
        ("subjectA_recording12_HAP_M.wav", Emotion.HAPPY, Sex.MALE, "subjectA_recording12"),
        ("weird-Name_ScA_f.wav", Emotion.SCARED, Sex.FEMALE, "weird-Name"),
    ],
)
def test_valid_names(name, emotion, sex, recording_id):
    stim = parse_stimulus_filename(name)
    assert stim is not None
    assert stim.emotion is emotion
    assert stim.sex is sex
    assert stim.recording_id == recording_id


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
    assert {s.sex for s in stimuli} == {Sex.FEMALE, Sex.MALE}
