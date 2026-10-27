# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Session modes and the PsychoPy audio-preference bootstrap (no window, no audio)."""

import pytest

from emognition.core import SessionMode


@pytest.mark.parametrize("value, label", [
    ("test", "Test"), ("passive", "Passive Training"), ("active", "Active Training"),
])
def test_session_mode_values_double_as_cli_arguments(value, label):
    mode = SessionMode(value)
    assert mode.value == value and mode.label == label


def test_configure_prefs_sets_the_legacy_audio_prefs():
    prefs = pytest.importorskip("psychopy").prefs
    from emognition.runtime import configure_prefs

    hardware = prefs.hardware
    saved_lib = list(hardware["audioLib"])
    had_mode, saved_mode = "audioLatencyMode" in hardware, hardware.get("audioLatencyMode")
    try:
        configure_prefs()
        assert list(hardware["audioLib"])[0] == "ptb" and hardware["audioLatencyMode"] == 1
    finally:
        hardware["audioLib"] = saved_lib
        if had_mode:
            hardware["audioLatencyMode"] = saved_mode
        else:
            hardware.pop("audioLatencyMode", None)


def test_psychopy_still_defaults_to_ptb_with_a_shared_latency_class():
    """PsychoPy 2026 ignores those prefs; what we rely on are these defaults.

    PTB schedules onsets sample-accurately (our RT zero), and latency class 1
    shares the device instead of grabbing it exclusively (class >= 2 was
    unstable under PipeWire here). If a PsychoPy upgrade changes either default,
    this fails before any participant hears anything different.
    """
    import inspect

    sound_mod = pytest.importorskip("psychopy.sound.sound")
    speaker = pytest.importorskip("psychopy.hardware.speaker")
    assert sound_mod.Sound.backend == "ptb"
    default = inspect.signature(speaker.SpeakerDevice.__init__).parameters["latencyClass"].default
    assert default == 1
