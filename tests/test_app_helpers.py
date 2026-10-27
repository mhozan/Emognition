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


# --- seed, timing QA and the JSON sidecar (Phase 5) ------------------------------

def test_sidecar_is_plain_json_with_iso_times_and_versions(tmp_path):
    import json

    from emognition.reports.sidecar import SIDECAR_FORMAT, environment_info, write_session_sidecar

    path = write_session_sidecar(str(tmp_path / "s.json"), {
        "random_seed": 42, "started_at": datetime(2026, 10, 27, 9, 0, 0), "environment": environment_info(),
    })
    data = json.load(open(path, encoding="utf-8"))
    assert data["format"] == SIDECAR_FORMAT and data["format_version"] == 1
    assert data["random_seed"] == 42 and data["started_at"] == "2026-10-27T09:00:00"
    assert data["environment"]["python"] and "psychopy" in data["environment"]["packages"]


def test_timing_rows_describe_seed_refresh_and_drops():
    rows = app._timing_rows(7, {"refresh_hz": 59.94, "refresh_measured": True, "frames_recorded": 12000,
                                "frames_dropped": 6, "audio_predicted_latency_ms": 9.6})
    assert rows == {"Random seed": "7", "Refresh rate": "59.9 Hz",
                    "Dropped frames": "6 of 12,000 (0.05%)", "Audio latency (predicted)": "9.6 ms"}
    assert app._timing_rows(1, {}) == {"Random seed": "1"}            # nothing measured: just the seed
    assert "(assumed)" in app._timing_rows(1, {"refresh_hz": 60.0})["Refresh rate"]


def test_sidecar_is_written_right_after_the_csv(tmp_path, monkeypatch):
    import emognition.reports as reports
    import emognition.reports.sidecar as sidecar

    order = []
    for module, name in ((reports, "write_csv_report"), (sidecar, "write_session_sidecar"),
                         (reports, "write_excel_report")):
        real = getattr(module, name)
        monkeypatch.setattr(module, name, lambda *a, _r=real, _n=name, **k: (order.append(_n), _r(*a, **k))[1])
    base = str(tmp_path / "P01_x")
    app._write_reports(_responses(), base, SessionInfo(participant="P01"), {"random_seed": 3})
    assert order[:3] == ["write_csv_report", "write_session_sidecar", "write_excel_report"]
    assert os.path.exists(base + ".json")


def test_seed_flag_is_accepted():
    assert app.build_parser().parse_args(["--participant=P", "--seed", "123"]).seed == 123
    assert app.build_parser().parse_args(["--participant=P"]).seed is None


# --- RT from the end of speech (Phase 5) -------------------------------------------------

def _clip(tmp_path, name, lead=0.2, speech=0.5, tail=0.6, rate=16000):
    import numpy as np
    import soundfile as sf

    t = np.arange(int(speech * rate)) / rate
    data = np.concatenate([np.zeros(int(lead * rate)), 0.2 * np.sin(2 * np.pi * 330 * t),
                           np.zeros(int(tail * rate))])
    path = tmp_path / name
    sf.write(str(path), data, rate, subtype="PCM_16")
    return str(path)


def test_speech_offset_rt_counts_from_the_end_of_speech_not_of_the_file(tmp_path):
    path = _clip(tmp_path, "a_hap_f.wav")                     # speech ends at 0.7 s; file at 1.3 s
    stim = Stimulus(path=path, emotion=Emotion.HAPPY, sex=Sex.FEMALE)
    answered = Response(stimulus=stim, responded=Emotion.HAPPY, rt_onset=1.6, rt_offset=0.3)
    unanswered = Response(stimulus=stim)
    spans = app._add_speech_offset_rts([answered, unanswered], [stim])
    assert answered.rt_speech_offset == pytest.approx(0.9, abs=0.02)   # 1.6 - 0.7
    assert unanswered.rt_speech_offset is None
    assert spans["a_hap_f.wav"] == pytest.approx([0.2, 0.7], abs=0.02)


def test_speech_offset_rt_survives_moved_or_missing_clips(tmp_path):
    moved = _clip(tmp_path, "b_sad_m.wav")
    old = Stimulus(path="/old/install/b_sad_m.wav", emotion=Emotion.SAD, sex=Sex.MALE)
    gone = Stimulus(path="/old/install/c_ang_f.wav", emotion=Emotion.ANGRY, sex=Sex.FEMALE)
    r1 = Response(stimulus=old, responded=Emotion.SAD, rt_onset=1.0, rt_offset=-0.3)
    r2 = Response(stimulus=gone, responded=Emotion.SAD, rt_onset=1.0, rt_offset=-0.3)
    app._add_speech_offset_rts([r1, r2], [Stimulus(path=moved, emotion=Emotion.SAD, sex=Sex.MALE)])
    assert r1.rt_speech_offset == pytest.approx(0.3, abs=0.02)        # found by name
    assert r2.rt_speech_offset is None                                 # unreadable: no value
