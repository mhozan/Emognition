# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the PDF report (headless matplotlib Agg + fpdf2)."""

from emognition.core import Emotion, Gender, Response, Stimulus
from emognition.reports import SessionInfo, write_pdf_report


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


def test_writes_valid_pdf(tmp_path):
    path = tmp_path / "report.pdf"
    out = write_pdf_report(_responses(), str(path),
                           info=SessionInfo(participant="P01"))
    assert out == str(path)
    data = path.read_bytes()
    assert data.startswith(b"%PDF-")          # valid PDF signature
    assert data.rstrip().endswith(b"%%EOF")   # complete file
    assert len(data) > 5000                    # embedded figures -> non-trivial size


def test_handles_unicode_participant(tmp_path):
    # A non-Latin-1 participant id must not crash the Latin-1 core-font PDF.
    path = tmp_path / "r.pdf"
    write_pdf_report(_responses(), str(path),
                     info=SessionInfo(participant="Pärticipant—✓"))
    assert path.read_bytes().startswith(b"%PDF-")
