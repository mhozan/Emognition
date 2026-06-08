# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the Excel report writer (round-trip: write then read back)."""

import pytest
from openpyxl import load_workbook

from emognition.core import Emotion, Sex, Response, Stimulus
from emognition.reports import SessionInfo, write_excel_report


def _resp(true, gender, responded, rt_offset=None, n_replays=0, fname="x_hap_f.wav"):
    stim = Stimulus(path=fname, emotion=true, sex=gender)
    rt_onset = None if rt_offset is None else rt_offset + 1.0
    return Response(stim, responded, rt_onset, rt_offset, n_replays)


# Same hand-checked scenario as the scoring tests (80%-ish, one miss, one blank):
#   Happy/F -> Happy ; Happy/M -> Sad ; Sad/F -> Sad ; Angry/M -> (none)
def _responses():
    return [
        _resp(Emotion.HAPPY, Sex.FEMALE, Emotion.HAPPY, 0.5, 0, "01_hap_f.wav"),
        _resp(Emotion.HAPPY, Sex.MALE, Emotion.SAD, 1.0, 1, "02_hap_m.wav"),
        _resp(Emotion.SAD, Sex.FEMALE, Emotion.SAD, 0.7, 0, "03_sad_f.wav"),
        _resp(Emotion.ANGRY, Sex.MALE, None, None, 0, "04_ang_m.wav"),
    ]


@pytest.fixture()
def workbook(tmp_path):
    path = tmp_path / "report.xlsx"
    write_excel_report(
        _responses(),
        str(path),
        info=SessionInfo(participant="P01", experimenter="Tester"),
    )
    return load_workbook(str(path))


def test_sheets_present(workbook):
    assert workbook.sheetnames == [
        "Session Info", "Confusion Matrix", "Percentages", "Pressed Keys"
    ]


def test_session_info(workbook):
    ws = workbook["Session Info"]
    assert ws["A1"].value.startswith("Emognition")
    # participant + experimenter values sit in column B of the metadata block
    column_b = [ws.cell(row=r, column=2).value for r in range(1, ws.max_row + 1)]
    assert "P01" in column_b and "Tester" in column_b


def test_confusion_matrix_cells(workbook):
    ws = workbook["Confusion Matrix"]
    # rows/cols order: Happy(2) Scared(3) Neutral(4) Sad(5) Angry(6)
    assert ws["B2"].value == 1   # Happy -> Happy
    assert ws["E2"].value == 1   # Happy -> Sad
    assert ws["E5"].value == 1   # Sad   -> Sad
    total = sum(
        (ws.cell(row=i, column=j).value or 0)
        for i in range(2, 7) for j in range(2, 7)
    )
    assert total == 3            # three answered trials


def test_percentages_total_accuracy(workbook):
    ws = workbook["Percentages"]
    # Rows: emotions 2-6, Female 7, Male 8, Unknown 9, Total 10. Column B = % correct.
    assert ws["A10"].value == "Total"
    assert ws["B10"].value == pytest.approx(200.0 / 3, abs=0.05)


def test_pressed_keys_rows(workbook):
    ws = workbook["Pressed Keys"]
    # Exactly 4 trial rows (column A = trial number); the legend in col J may
    # extend a row further, so assert on the data column rather than max_row.
    trial_numbers = [
        ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)
    ]
    assert [t for t in trial_numbers if t is not None] == [1, 2, 3, 4]
    # Last trial (Angry, no response): Pressed empty, Correct? False.
    assert ws.cell(row=5, column=2).value == "04_ang_m.wav"
    assert ws.cell(row=5, column=4).value is None      # no pressed key
    assert ws.cell(row=5, column=5).value is False     # not correct
    # Legend present in column K (col J is now the RT-flag column).
    assert ws.cell(row=2, column=11).value == "1: Happy"
