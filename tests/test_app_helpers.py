# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Pure helpers of the session runner (emognition/app.py) -- no window, no audio."""

import io
import os
from datetime import datetime

import pytest

from emognition import app
from emognition.core import Emotion, Response, Sex, Stimulus
from emognition.reports import SessionInfo


def test_parse_emotions_accepts_tags_and_names_in_any_case():
    assert app._parse_emotions("Happy, sad,ANG") == [Emotion.HAPPY, Emotion.SAD, Emotion.ANGRY]
    assert app._parse_emotions("hap,happy") == [Emotion.HAPPY]          # duplicates collapse
    assert app._parse_emotions("") is None and app._parse_emotions(None) is None


def test_parse_emotions_rejects_unknown_entries():
    with pytest.raises(ValueError, match="joyful"):
        app._parse_emotions("hap,joyful")


def test_report_base_keeps_only_safe_characters(tmp_path):
    base = app._report_base(str(tmp_path), "../P 01/é", datetime(2026, 10, 27, 9, 5, 7))
    assert os.path.dirname(base) == str(tmp_path)                       # no path traversal
    assert os.path.basename(base) == "P01é_20261027_090507"
    assert os.path.basename(app._report_base(str(tmp_path), "///", datetime(2026, 1, 1))) \
        .startswith("session_")


def test_prepare_save_dir_creates_and_checks(tmp_path):
    target = tmp_path / "out" / "deep"
    assert app._prepare_save_dir(str(target)) == str(target) and target.is_dir()
    assert os.listdir(target) == []                                     # probe file cleaned up
    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    with pytest.raises(OSError):
        app._prepare_save_dir(str(blocker / "sub"))


def _responses():
    stim = Stimulus(path="/clips/01_hap_f.wav", emotion=Emotion.HAPPY, sex=Sex.FEMALE)
    return [Response(stimulus=stim, responded=Emotion.HAPPY, rt_onset=1.4, rt_offset=0.4)]


def test_write_reports_writes_csv_first_and_survives_a_failing_format(tmp_path, monkeypatch):
    import emognition.reports as reports

    order = []
    real_csv = reports.write_csv_report

    def tracking_csv(*a, **k):
        order.append("CSV")
        return real_csv(*a, **k)

    def broken_pdf(*a, **k):
        order.append("PDF")
        raise RuntimeError("no fonts")

    monkeypatch.setattr(reports, "write_csv_report", tracking_csv)
    monkeypatch.setattr(reports, "write_pdf_report", broken_pdf)
    base = str(tmp_path / "P01_x")
    html, failed = app._write_reports(_responses(), base, SessionInfo(participant="P01"))
    assert order[0] == "CSV" and failed == ["PDF"]
    for ext in (".csv", "_summary.csv", ".xlsx", ".html"):
        assert os.path.exists(base + ext)
    assert html == base + ".html"


def test_emit_survives_a_broken_pipe(monkeypatch):
    class BrokenStdout(io.StringIO):
        def write(self, _text):
            raise BrokenPipeError("parent went away")

    monkeypatch.setattr("sys.stdout", BrokenStdout())
    app._emit({"status": "done"})          # must not raise
