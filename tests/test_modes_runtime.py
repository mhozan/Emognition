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
    ("test", "Test"), ("passive", "Familiarization"), ("active", "Practice"),
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


def test_playback_resolves_to_ptb_with_a_shared_latency_class():
    """What our RTs rely on: PTB playback at latency class 1 (a shared device).

    PTB schedules onsets sample-accurately (our RT zero), and latency class 1
    shares the device instead of grabbing it exclusively (class >= 2 was
    unstable under PipeWire here). PsychoPy has moved where both are decided
    (2026.1 hard-wired them; 2026.2 reads ``prefs.hardware['audioLib']`` again),
    so this checks the outcome with our prefs applied: if an upgrade changes it,
    this fails before any participant hears anything different.
    """
    import inspect

    prefs = pytest.importorskip("psychopy").prefs
    from emognition.runtime import configure_prefs

    saved = list(prefs.hardware["audioLib"])
    try:
        configure_prefs()
        sound_mod = pytest.importorskip("psychopy.sound.sound")
        speaker_mod = pytest.importorskip("psychopy.hardware.speaker")
        assert sound_mod.Sound.resolveBackend().__name__ == "psychopy.sound.backend_ptb"
        device = speaker_mod.SpeakerDevice.resolveBackend()
        assert device.__name__ == "PsychtoolboxSpeakerDevice"
        assert inspect.signature(device.__init__).parameters["latencyClass"].default == 1
    finally:
        prefs.hardware["audioLib"] = saved


# --- PsychToolbox audio vs Python 3.12+ on Linux (runtime.ptb_audio_problem) ----

@pytest.mark.parametrize("version, platform, realtime, crashes", [
    ((3, 12), "linux", False, True),       # the crash: PTB prints from its audio thread
    ((3, 15), "linux", False, True),
    ((3, 12), "linux", True, False),       # realtime allowed: PTB has nothing to complain about
    ((3, 11), "linux", False, False),      # 3.11 survives the print (process-wide thread state)
    ((3, 12), "win32", False, False),      # the realtime switch is Linux-only
    ((3, 12), "darwin", False, False),
])
def test_ptb_audio_problem_flags_exactly_the_crashing_setup(version, platform, realtime, crashes):
    from emognition.runtime import ptb_audio_problem

    problem = ptb_audio_problem(version, platform, realtime_allowed=lambda: realtime)
    assert (problem is not None) == crashes
    if crashes:
        assert "Python 3.11" in problem and "rtprio" in problem


def test_realtime_probe_answers_without_changing_this_thread():
    import os
    import sys

    from emognition.runtime import _realtime_allowed

    if not sys.platform.startswith("linux"):
        pytest.skip("scheduling policies are probed on Linux only")
    before = os.sched_getscheduler(0)
    assert isinstance(_realtime_allowed(), bool)
    assert os.sched_getscheduler(0) == before      # only the throwaway thread was touched
