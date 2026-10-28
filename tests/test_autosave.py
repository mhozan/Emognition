# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Crash-safe autosave log (emognition/io/autosave.py) and the resume helpers."""

import os
import time
from datetime import datetime

import pytest

from emognition import app
from emognition.config import resume_argv, session_file_pattern
from emognition.core import Emotion, Response, Sex, Stimulus
from emognition.io.autosave import (
    LOG_FORMAT,
    PARTIAL_SUFFIX,
    SessionLog,
    find_interrupted,
    read_session_log,
    response_from_record,
    response_to_record,
)

HEADER = {"participant": "P1", "started_at": datetime(2026, 10, 27, 14, 3, 5),
          "random_seed": 42, "trial_order": ["/c/a_hap_f.wav", "/c/b_sad_m.wav"]}


def _trial(name="spk1_hap_f.wav", emotion=Emotion.HAPPY, responded=Emotion.HAPPY, rt=0.512,
           n_pauses=0):
    stim = Stimulus(path=f"/clips/{name}", emotion=emotion, sex=Sex.FEMALE, recording_id="spk1")
    return Response(stimulus=stim, responded=responded,
                    rt_onset=None if rt is None else rt + 1.25, rt_offset=rt,
                    n_replays=1, background="Starry night", n_pauses=n_pauses)


@pytest.mark.parametrize("response", [
    _trial(),
    _trial(responded=None, rt=None),                       # unanswered trial
    _trial(name="x_ang_f.wav", emotion=Emotion.ANGRY, responded=Emotion.SAD, rt=-0.0371),
    _trial(n_pauses=2),                                    # paused twice, replayed each time
    Response(Stimulus("/c/x_sad_f.wav", Emotion.SAD, Sex.FEMALE), Emotion.ANGRY, 1.5, 0.6,
             choices=(Emotion.ANGRY, Emotion.HAPPY, Emotion.SAD)),   # retried until correct
])
def test_records_round_trip_exactly(response):
    assert response_from_record(response_to_record(response)) == response


def test_log_keeps_header_and_trials_and_skips_a_torn_last_line(tmp_path):
    path = str(tmp_path / f"P1_20261027_140305{PARTIAL_SUFFIX}")
    log = SessionLog(path, HEADER)
    first, second = _trial(), _trial(name="y_sad_f.wav", emotion=Emotion.SAD, rt=1.0)
    log.append(first)
    log.append(second)
    log.close()
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"trial": {"file": "/clips/z_ne')          # the write a crash interrupted
    header, trials = read_session_log(path)
    assert header["format"] == LOG_FORMAT and header["random_seed"] == 42
    assert datetime.fromisoformat(header["started_at"]) == HEADER["started_at"]
    assert trials == [first, second]


def test_a_continued_log_appends_and_a_new_one_never_overwrites(tmp_path):
    path = str(tmp_path / "s.partial.jsonl")
    SessionLog(path, HEADER).close()
    with pytest.raises(FileExistsError):
        SessionLog(path, HEADER)                              # an existing log is data
    again = SessionLog(path)                                  # header=None: carry on
    again.append(_trial())
    again.close()
    assert len(read_session_log(path)[1]) == 1


def test_discard_removes_the_log_once_reports_are_safe(tmp_path):
    path = str(tmp_path / "s.partial.jsonl")
    log = SessionLog(path, HEADER)
    log.discard()
    log.discard()                                             # idempotent
    assert not os.path.exists(path)


def test_clearing_moves_a_log_aside_and_keeps_its_id_used(tmp_path):
    from emognition.config import next_participant_id
    from emognition.io.autosave import clear_session

    path = str(tmp_path / f"sub-003_20261027_101500{PARTIAL_SUFFIX}")
    SessionLog(path, HEADER).close()
    moved = clear_session(path)
    assert not os.path.exists(path) and moved == str(tmp_path / "cleared" / os.path.basename(path))
    assert find_interrupted(str(tmp_path)) == []                  # no longer offered for Resume
    assert len(read_session_log(moved)[0]) > 0                    # but nothing was lost
    assert next_participant_id(str(tmp_path)) == "sub-004"        # and the ID isn't handed out again
    SessionLog(path, HEADER).close()                              # the same name, cleared again:
    assert clear_session(path).endswith(f"-2{PARTIAL_SUFFIX}")    # never overwrites


@pytest.mark.parametrize("content", ["", '{"not": "a log"}\n', "garbage\n"])
def test_other_files_are_rejected(tmp_path, content):
    path = tmp_path / "other.partial.jsonl"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        read_session_log(str(path))


def test_find_interrupted_is_per_participant_and_newest_first(tmp_path):
    def touch(name, age):
        p = tmp_path / name
        p.write_text("{}\n")
        stamp = time.time() - age
        os.utime(p, (stamp, stamp))
        return str(p)

    old = touch(f"P1_20261001_090000{PARTIAL_SUFFIX}", 100)
    new = touch(f"P1_20261027_090000{PARTIAL_SUFFIX}", 10)
    other = touch(f"P1_retest_20261027_090000{PARTIAL_SUFFIX}", 5)   # someone else
    touch("P1_20261027_090000.csv", 1)                                # not a log
    assert find_interrupted(str(tmp_path), "P1") == [new, old]
    assert find_interrupted(str(tmp_path), "P1_retest") == [other]
    assert find_interrupted(str(tmp_path)) == [other, new, old]
    assert find_interrupted(str(tmp_path / "missing"), "P1") == []


def test_session_file_pattern_matches_whole_names_only():
    mine = session_file_pattern("P 1", ".csv")                        # stem "P1"
    assert mine.fullmatch("P1_20261027_090000.csv")
    assert not mine.fullmatch("P1_retest_20261027_090000.csv")
    assert not mine.fullmatch("P1_20261027_090000_confusion.csv")


# --- resume helpers in app.py ---------------------------------------------------

def test_resume_argv_round_trips_through_the_real_parser():
    args = app.build_parser().parse_args(resume_argv("/data/-odd name.partial.jsonl", 1, True))
    assert args.resume == "/data/-odd name.partial.jsonl"
    assert args.screen == 1 and args.fullscreen


def test_saved_settings_win_except_the_display():
    args = app.build_parser().parse_args(resume_argv("/x.partial.jsonl", screen=2))
    saved = {"participant": "P7", "mode": "active", "volume": 0.5, "screen": 0,
             "fullscreen": True, "resume": None, "from_a_newer_version": 1}
    app._apply_saved_settings(args, saved)
    assert (args.participant, args.mode, args.volume) == ("P7", "active", 0.5)
    assert args.screen == 2 and not args.fullscreen and args.resume == "/x.partial.jsonl"
    assert not hasattr(args, "from_a_newer_version")


def test_resumed_trials_are_found_again_even_if_the_app_moved(tmp_path):
    clips = tmp_path / "clips"
    clips.mkdir()
    for name in ("spk1_hap_f.wav", "spk2_sad_m.wav"):
        (clips / name).write_bytes(b"")
    trials = app._stimuli_from_paths(
        [str(clips / "spk1_hap_f.wav"), "/old/install/assets/audio/spk2_sad_m.wav"], str(clips))
    assert [t.emotion for t in trials] == [Emotion.HAPPY, Emotion.SAD]
    assert trials[1].path == str(clips / "spk2_sad_m.wav")
    with pytest.raises(ValueError, match="gone_ang_f.wav"):
        app._stimuli_from_paths(["/old/gone_ang_f.wav"], str(clips))
