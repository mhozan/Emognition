# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The four report formats must agree with each other (and with Excel's rounding)."""

import csv

import pytest
from openpyxl import load_workbook

from emognition.core import Emotion, Response, Sex, Stimulus, summarize
from emognition.reports import SessionInfo, write_csv_report, write_excel_report
from emognition.reports.common import (
    EMPTY,
    fmt_pct,
    fmt_pct_unit,
    fmt_replays,
    fmt_seconds,
    fmt_seconds_unit,
    prepare_summary,
)


@pytest.mark.parametrize("fmt, value, text", [
    (fmt_pct, 6.25, "6.3"),        # Python's f"{6.25:.1f}" gives 6.2; Excel shows 6.3
    (fmt_pct, 62.5, "62.5"),
    (fmt_seconds, 0.0005, "0.001"),
    (fmt_seconds, 2.675, "2.675"),
    (fmt_replays, 0.125, "0.13"),  # f"{0.125:.2f}" gives 0.12
])
def test_ties_round_half_up_like_excel(fmt, value, text):
    assert fmt(value) == text


def test_missing_values_never_get_a_unit():
    assert fmt_pct_unit(None) == EMPTY and fmt_seconds_unit(None) == EMPTY
    assert fmt_pct_unit(50.0) == "50.0%" and fmt_seconds_unit(0.5) == "0.500 s"


def _responses():
    stim = lambda emo, n: Stimulus(path=f"/c/{n}.wav", emotion=emo, sex=Sex.MALE)  # noqa: E731
    return [
        Response(stimulus=stim(Emotion.SAD, i), responded=Emotion.SAD,
                 rt_onset=1.5 + 0.01 * i, rt_offset=0.5 + 0.01 * i)
        for i in range(8)
    ] + [Response(stimulus=stim(Emotion.SAD, 9), responded=Emotion.SAD, rt_onset=40.0, rt_offset=39.0)]


def test_summary_csv_counts_the_rts_behind_each_mean(tmp_path):
    _, summary_path = write_csv_report(_responses(), str(tmp_path / "r.csv"))
    rows = {row["group"]: row for row in csv.DictReader(open(summary_path, newline="", encoding="utf-8"))}
    assert rows["Total"]["n_answered"] == "9" and rows["Total"]["n_rt"] == "8"   # 1 slow outlier left out


def test_excel_says_when_means_exclude_flagged_trials(tmp_path):
    path = write_excel_report(_responses(), str(tmp_path / "r.xlsx"), info=SessionInfo())
    ws = load_workbook(path)["Percentages"]
    notes = [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str)]
    assert any("exclude 1 trial" in n for n in notes)


def test_a_summary_with_the_other_rt_basis_is_rejected():
    onset_summary = summarize(_responses(), rt_kind="onset")
    with pytest.raises(ValueError, match="onset"):
        prepare_summary(_responses(), summary=onset_summary, rt_kind="offset")
