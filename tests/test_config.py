# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for ExperimentSettings -> CLI argv and JSON persistence (UI-free)."""

from emognition.config import ExperimentSettings


def test_default_argv_is_minimal():
    argv = ExperimentSettings().to_argv()
    assert argv[:2] == ["--participant", "Participant01"]
    assert "--caption" in argv and "none" in argv
    # defaults: shuffle on, no replays/viz/fullscreen, full emotion set
    for flag in ("--no-shuffle", "--allow-replays", "--amp-visualizer",
                 "--fullscreen", "--emotions", "--audio-dir", "--save-dir"):
        assert flag not in argv


def test_argv_reflects_toggles_and_subset():
    s = ExperimentSettings(
        participant="P02", audio_dir="/data/clips", save_dir="/out",
        fullscreen=True, shuffle=False, allow_replays=True, amp_visualizer=True,
        emotions=["hap", "sad"],
    )
    argv = s.to_argv()
    assert "--fullscreen" in argv and "--no-shuffle" in argv
    assert "--allow-replays" in argv and "--amp-visualizer" in argv
    assert argv[argv.index("--audio-dir") + 1] == "/data/clips"
    assert argv[argv.index("--save-dir") + 1] == "/out"
    assert argv[argv.index("--emotions") + 1] == "hap,sad"


def test_json_round_trip(tmp_path):
    s = ExperimentSettings(participant="P03", allow_replays=True, emotions=["neu"])
    path = s.save(str(tmp_path / "settings.json"))
    back = ExperimentSettings.load(path)
    assert back == s


def test_load_ignores_unknown_keys(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"participant": "P04", "obsolete_field": 123}', encoding="utf-8")
    s = ExperimentSettings.load(str(p))
    assert s.participant == "P04"  # unknown key ignored, no crash
