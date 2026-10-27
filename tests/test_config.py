# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for ExperimentSettings -> CLI argv and JSON persistence (UI-free).

The argv is checked by parsing it with the app's real argument parser, so a
mismatch between what the setup window sends and what the CLI accepts fails here.
"""

from emognition.app import build_parser
from emognition.config import ExperimentSettings


def _parse(settings: ExperimentSettings):
    return build_parser().parse_args(settings.to_argv())


def test_default_argv_is_minimal():
    argv = ExperimentSettings().to_argv()
    assert argv[:2] == ["--participant=Participant01", "--experimenter=APPstaff"]
    # defaults: shuffle on, no replays/viz/fullscreen, full emotion set, default background
    for flag in ("--no-shuffle", "--allow-replays", "--amp-visualizer", "--fullscreen",
                 "--emotions", "--audio-dir", "--save-dir", "--background",
                 "--background-every", "--no-background-shuffle"):
        assert not any(a == flag or a.startswith(flag + "=") for a in argv)
    args = _parse(ExperimentSettings())
    assert args.participant == "Participant01" and args.caption == "none"
    assert args.background == "default" and args.background_every == 5 and args.background_shuffle


def test_argv_reflects_toggles_and_subset():
    s = ExperimentSettings(
        participant="P02", audio_dir="/data/clips", save_dir="/out",
        fullscreen=True, shuffle=False, allow_replays=True, amp_visualizer=True,
        emotions=["hap", "sad"],
    )
    args = _parse(s)
    assert args.fullscreen and args.no_shuffle and args.allow_replays and args.amp_visualizer
    assert args.audio_dir == "/data/clips" and args.save_dir == "/out"
    assert args.emotions == "hap,sad"


def test_argv_carries_background_settings():
    s = ExperimentSettings(background="/pics/sea.jpg", background_every=3, background_shuffle=False)
    args = _parse(s)
    assert args.background == "/pics/sea.jpg"
    assert args.background_every == 3 and not args.background_shuffle


def test_values_starting_with_a_dash_survive_the_command_line():
    s = ExperimentSettings(participant="-P01", experimenter="--lab", background="-odd.png")
    args = _parse(s)
    assert (args.participant, args.experimenter, args.background) == ("-P01", "--lab", "-odd.png")


def test_json_round_trip(tmp_path):
    s = ExperimentSettings(participant="P03", allow_replays=True, emotions=["neu"],
                           background="slideshow", background_every=2)
    path = s.save(str(tmp_path / "settings.json"))
    back = ExperimentSettings.load(path)
    assert back == s


def test_load_ignores_unknown_keys(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"participant": "P04", "obsolete_field": 123}', encoding="utf-8")
    s = ExperimentSettings.load(str(p))
    assert s.participant == "P04"  # unknown key ignored, no crash


def test_old_settings_files_get_background_defaults(tmp_path):
    p = tmp_path / "old.json"
    p.write_text('{"participant": "P05", "mode": "active"}', encoding="utf-8")
    s = ExperimentSettings.load(str(p))
    assert (s.background, s.background_every, s.background_shuffle) == ("default", 5, True)


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path):
    path = str(tmp_path / "settings.json")
    ExperimentSettings(participant="A").save(path)
    ExperimentSettings(participant="B").save(path)
    assert ExperimentSettings.load(path).participant == "B"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.json"]


def test_participant_file_stem_is_path_safe():
    from emognition.config import participant_file_stem

    assert participant_file_stem("../P 01/é") == "P01é"
    assert participant_file_stem("///") == "session"
