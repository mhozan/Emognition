# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""PDF report (fpdf2 + matplotlib) — the FOSS replacement for MATLAB print -dpdf.

Distinct from the browser "print the HTML" route: this generates a real PDF
headlessly (no browser), so it works in batch/automated pipelines. Layout via
fpdf2; the confusion matrix and reaction-time plots are matplotlib PNGs embedded
as images. Same inputs and prepare_summary() as the other writers, so every
report format agrees.

Note: fpdf2's built-in fonts are Latin-1, so dynamic text is sanitised to ASCII
(em dash -> '-', check/cross -> 'Y'/'N') via :func:`_ascii`.
"""

from __future__ import annotations

import io
from collections.abc import Sequence

from fpdf import FPDF

from ..core import EMOTIONS_IN_ORDER, SEXES_IN_ORDER, Response, SessionSummary
from ..core.scoring import DEFAULT_RT_KIND, GroupStats
from .charts_mpl import confusion_png, reaction_time_png
from .common import (
    RT_FLAG_LABEL,
    STAT_COLUMNS,
    SessionInfo,
    fmt_datetime,
    fmt_pct,
    fmt_replays,
    fmt_seconds,
    prepare_summary,
)


def _ascii(value: object) -> str:
    """Make a string safe for fpdf2's Latin-1 core fonts."""
    s = str(value).replace("—", "-").replace("✓", "Y").replace("✗", "N")
    return s.encode("latin-1", "replace").decode("latin-1")


def _stat_row(label: str, stats: GroupStats) -> list[str]:
    return [
        label,
        _ascii(fmt_pct(stats.pct_correct)),
        _ascii(fmt_seconds(stats.mean_rt)),
        _ascii(fmt_replays(stats.mean_replays)),
    ]


def _header(pdf: FPDF, info: SessionInfo) -> None:
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Emognition - Session Report", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 7, _ascii(info.participant or "Unnamed participant"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)


def _session_info(pdf: FPDF, info: SessionInfo, summary: SessionSummary) -> None:
    rows = [
        ("Experimenter", info.experimenter),
        ("Mode", info.mode),
        ("Started", fmt_datetime(info.started_at)),
        ("Finished", fmt_datetime(info.finished_at)),
        ("Trials", f"{summary.total.n_answered}/{summary.total.n_presented} answered, "
                   f"{summary.total.n_correct} correct"),
        ("Overall accuracy", f"{fmt_pct(summary.total.pct_correct)}%"),
        ("Mean reaction", f"{fmt_seconds(summary.total.mean_rt)} s "
                          f"(from {summary.rt_kind})"),
    ]
    pdf.set_font("Helvetica", "", 10)
    for key, val in rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 6, _ascii(key))
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, _ascii(val), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _image(pdf: FPDF, png: bytes, width: float) -> None:
    pdf.image(io.BytesIO(png), w=width)
    pdf.ln(2)


def _section_title(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, _ascii(text), new_x="LMARGIN", new_y="NEXT")


def _stats_table(pdf: FPDF, summary: SessionSummary) -> None:
    pdf.set_font("Helvetica", "", 9)
    rows = [["", *STAT_COLUMNS]]
    for emo in summary.emotion_order:
        rows.append(_stat_row(emo.label, summary.per_emotion[emo]))
    for sex in SEXES_IN_ORDER:
        rows.append(_stat_row(sex.label, summary.per_sex[sex]))
    rows.append(_stat_row("Total", summary.total))
    with pdf.table(text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT")) as table:
        for r in rows:
            table.row([_ascii(c) for c in r])
    pdf.ln(2)


def _trials_table(pdf: FPDF, responses: Sequence[Response], flags) -> None:
    pdf.set_font("Helvetica", "", 8)
    header = ["#", "File", "Played", "Chosen", "OK",
              "RT on", "RT off", "Rep", "Flag"]
    rows = [header]
    for i, (r, flag) in enumerate(zip(responses, flags), start=1):
        rows.append([
            str(i),
            _ascii(r.stimulus.filename),
            r.true_emotion.label,
            r.responded.label if r.responded else "-",
            "Y" if r.is_correct else ("N" if r.answered else "-"),
            _ascii(fmt_seconds(r.rt_onset)),
            _ascii(fmt_seconds(r.rt_offset)),
            str(r.n_replays),
            RT_FLAG_LABEL[flag] or "ok",
        ])
    with pdf.table() as table:
        for r in rows:
            table.row([_ascii(c) for c in r])


def write_pdf_report(
    responses: Sequence[Response],
    path: str,
    *,
    summary: SessionSummary | None = None,
    info: SessionInfo | None = None,
    rt_kind: str = DEFAULT_RT_KIND,
) -> str:
    """Render the full PDF report to *path* and return it."""
    summary, flags = prepare_summary(responses, summary=summary, rt_kind=rt_kind)
    info = info or SessionInfo(rt_kind=rt_kind)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _header(pdf, info)
    _session_info(pdf, info, summary)

    _section_title(pdf, "Confusion matrix (rows = played, cols = chosen)")
    _image(pdf, confusion_png(summary), width=95)

    _section_title(pdf, "Statistics")
    _stats_table(pdf, summary)

    _section_title(pdf, "Reaction time per trial")
    _image(pdf, reaction_time_png(responses), width=165)

    _section_title(pdf, "Per-trial detail")
    _trials_table(pdf, responses, flags)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.ln(2)
    pdf.multi_cell(0, 4, _ascii(
        "Reaction-time means exclude anticipatory/outlier trials (flagged above); "
        "accuracy uses all answered trials. Generated by Emognition (AGPL-3.0)."
    ))

    pdf.output(path)
    return path
