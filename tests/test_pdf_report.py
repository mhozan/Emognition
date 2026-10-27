# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the PDF report (headless matplotlib Agg + fpdf2)."""

from emognition.core import Emotion, Sex, Response, Stimulus
from emognition.reports import SessionInfo, write_pdf_report


def _resp(true, gender, responded, rt_offset=None, fname="x_hap_f.wav"):
    stim = Stimulus(path=fname, emotion=true, sex=gender)
    rt_onset = None if rt_offset is None else rt_offset + 1.0
    return Response(stim, responded, rt_onset, rt_offset, 0)


def _responses():
    return [
        _resp(Emotion.HAPPY, Sex.FEMALE, Emotion.HAPPY, 0.5, "01_hap_f.wav"),
        _resp(Emotion.HAPPY, Sex.MALE, Emotion.SAD, 1.0, "02_hap_m.wav"),
        _resp(Emotion.SAD, Sex.FEMALE, Emotion.SAD, 0.7, "03_sad_f.wav"),
        _resp(Emotion.ANGRY, Sex.MALE, None, None, "04_ang_m.wav"),
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


def _pdf_text(data: bytes) -> str:
    """Text drawn in a PDF written by fpdf2 (inflate its content streams)."""
    import re
    import zlib

    chunks = []
    for stream in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            chunks.append(zlib.decompress(stream).decode("latin-1"))
        except zlib.error:
            continue                              # images etc.
    return "".join(chunks)


def test_pdf_shows_the_session_details_and_numbers(tmp_path):
    path = tmp_path / "r.pdf"
    write_pdf_report(_responses(), str(path),
                     info=SessionInfo(participant="P01", experimenter="Dr Lee",
                                      background="Rolling hills", audio_folder="/clips"))
    text = _pdf_text(path.read_bytes())
    for expected in ("Session Report", "P01", "Dr Lee", "Rolling hills", "/clips",
                     "66.7%", "04_ang_m.wav"):
        assert expected in text, expected
    assert "-%" not in text                       # no unit after a missing value
