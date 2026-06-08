# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for CSV export (read back with the csv module and check rows)."""

import csv

from emognition.core import Emotion, Gender, Response, Stimulus
from emognition.reports import write_csv_report


def _resp(true, gender, responded, rt_offset=None, fname="x_hap_f.wav"):
    stim = Stimulus(path=fname, emotion=true, gender=gender)
    rt_onset = None if rt_offset is None else rt_offset + 1.0
    return Response(stim, responded, rt_onset, rt_offset, 0)


def _responses():
    return [
        _resp(Emotion.HAPPY, Gender.FEMALE, Emotion.HAPPY, 0.5, "01_hap_f.wav"),
        _resp(Emotion.HAPPY, Gender.MALE, Emotion.SAD, 1.0, "02_hap_m.wav"),
        _resp(Emotion.SAD, Gender.FEMALE, Emotion.SAD, 0.7, "03_sad_f.wav"),
        _resp(Emotion.ANGRY, Gender.MALE, None, None, "04_ang_m.wav"),
    ]


def test_writes_two_files(tmp_path):
    base = tmp_path / "out.csv"
    paths = write_csv_report(_responses(), str(base))
    assert len(paths) == 2
    assert paths[0].endswith("out.csv")
    assert paths[1].endswith("out_summary.csv")


def test_trials_csv_rows_and_values(tmp_path):
    base = tmp_path / "out.csv"
    trials_path, _ = write_csv_report(_responses(), str(base))
    with open(trials_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 4

    r0 = rows[0]
    assert r0["audio_file"] == "01_hap_f.wav"
    assert r0["true_emotion"] == "Happy" and r0["true_code"] == "1"
    assert r0["correct"] == "1"
    assert r0["gender"] == "female"

    # Unanswered trial: blank chosen fields, correct=0.
    r3 = rows[3]
    assert r3["chosen_emotion"] == "" and r3["chosen_code"] == ""
    assert r3["correct"] == "0"
    assert r3["rt_flag"] == "no response"


def test_summary_csv_total_row(tmp_path):
    base = tmp_path / "out.csv"
    _, summary_path = write_csv_report(_responses(), str(base))
    with open(summary_path, newline="", encoding="utf-8") as fh:
        rows = {row["group"]: row for row in csv.DictReader(fh)}
    assert set(rows) >= {"Happy", "Female", "Male", "Total"}
    assert rows["Total"]["n_answered"] == "3"
    assert abs(float(rows["Total"]["pct_correct"]) - 200.0 / 3) < 0.05
