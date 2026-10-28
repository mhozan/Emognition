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
    assert argv[:2] == ["--participant=sub-001", "--experimenter=APPstaff"]
    # defaults: shuffle on, no replays/viz, full emotion set, default background
    for flag in ("--no-shuffle", "--allow-replays", "--amp-visualizer",
                 "--emotions", "--audio-dir", "--save-dir", "--background",
                 "--background-every", "--no-background-shuffle", "--background-first"):
        assert not any(a == flag or a.startswith(flag + "=") for a in argv)
    args = _parse(ExperimentSettings())
    assert args.participant == "sub-001" and args.caption == "none"
    assert args.fullscreen and args.mode == "test"                  # full screen by default
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
    assert s.retry_until_correct is False


def test_replay_limit_reaches_the_command_line():
    args = _parse(ExperimentSettings(allow_replays=True, max_replays=2))
    assert args.allow_replays and args.max_replays == 2
    args = _parse(ExperimentSettings(allow_replays=True))                 # 0 = no limit
    assert args.allow_replays and args.max_replays == 0
    assert _parse(ExperimentSettings(max_replays=3)).allow_replays is False  # off means off


def test_participant_ids_are_bids_style_and_never_collide(tmp_path):
    from emognition.config import amend_participant_id, has_reports, next_participant_id

    assert next_participant_id(str(tmp_path)) == "sub-001"
    for name in ("sub-001_20261027_101500.csv", "sub-003_20261027_101600.csv",
                 "sub-004_20261027_101700.partial.jsonl", "jane_20261027_101800.csv",
                 "sub-003_20261027_101600_confusion.csv"):
        (tmp_path / name).write_text("x")
    assert next_participant_id(str(tmp_path)) == "sub-005"      # after the highest, logs too
    assert amend_participant_id("sub-003", str(tmp_path)) == "sub-005"
    assert amend_participant_id("jane", str(tmp_path)) == "jane2"
    assert has_reports("sub-003", str(tmp_path)) and not has_reports("sub-004", str(tmp_path))


def test_pacing_options_reach_the_command_line():
    args = _parse(ExperimentSettings())
    assert (args.next_button, args.stars_every, args.break_every) == (False, 0, 0)
    args = _parse(ExperimentSettings(next_button=True, stars_every=5, break_every=20))
    assert (args.next_button, args.stars_every, args.break_every) == (True, 5, 20)


def test_ordering_reaches_the_command_line():
    assert _parse(ExperimentSettings(max_run=2)).max_run == 2
    assert _parse(ExperimentSettings()).max_run == 0


def test_practice_trials_are_gone():
    import pytest

    assert not hasattr(ExperimentSettings(), "practice")
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--practice", "3"])


def test_the_slideshow_switch_starts_with_the_chosen_picture(tmp_path):
    picture = tmp_path / "sea.jpg"
    picture.write_bytes(b"not decoded here")
    on = ExperimentSettings(background=str(picture), slideshow=True)
    args = _parse(on)
    assert (args.background, args.background_first) == ("slideshow", str(picture))
    assert _parse(ExperimentSettings(slideshow=True)).background_first is None   # gradient: none
    off = _parse(ExperimentSettings(background=str(picture)))
    assert (off.background, off.background_first) == (str(picture), None)


def test_a_slideshow_saved_the_old_way_loads_as_the_switch(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"background": "slideshow", "background_every": 3}', encoding="utf-8")
    s = ExperimentSettings.load(str(path))
    assert (s.background, s.slideshow, s.background_every) == ("default", True, 3)


def test_negative_every_n_is_refused():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(["--stars-every", "-1"])


def test_retry_until_correct_reaches_the_command_line():
    assert not _parse(ExperimentSettings(mode="active")).retry_until_correct
    args = _parse(ExperimentSettings(mode="active", retry_until_correct=True))
    assert args.retry_until_correct and args.mode == "active"


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
