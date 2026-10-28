# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Plain CSV export -- the format every stats tool (R, Python, JASP, SPSS) reads.

Two flat tables, both stdlib ``csv`` only:

* a **per-trial** CSV (one row per presentation), and
* a **summary** CSV (per-emotion / sex / total stats).

Gotcha worth knowing: always open CSV files with ``newline=""``. The csv module
writes its own line terminator (``\\r\\n``); if you let the text layer also
translate newlines (the default), Windows ends up with a blank line between every
row. ``newline=""`` disables that translation so the csv module is in charge.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Sequence

from ..core import SEXES_IN_ORDER, Response, SessionSummary
from ..core.scoring import DEFAULT_RT_KIND, GroupStats
from ..io.spreadsheet import neutralize
from .common import RT_FLAG_LABEL, prepare_summary, round_half_up

_TRIAL_FIELDS = [
    "trial",
    "audio_file",
    "recording_id",
    "true_emotion",
    "true_code",
    "chosen_emotion",
    "chosen_code",
    "correct",
    "rt_onset_s",
    "rt_offset_s",
    "replays",
    "sex",
    "rt_flag",
    "background",      # picture on screen during the trial ("" = plain)
    "pauses",          # times the trial was paused/interrupted, then replayed
    "attempts",        # answers given (more than 1 = practice's retries)
    "choices",         # every answer in order when retried, e.g. "Sad > Happy"
    "rt_speech_offset_s",  # RT from the detected end of speech, not of the file
]

_SUMMARY_FIELDS = [
    "group",
    "n_presented",
    "n_answered",
    "n_correct",
    "pct_correct",
    "mean_rt_s",
    "mean_replays",
    "n_rt",            # RTs averaged into mean_rt_s (flagged trials excluded)
    "median_rt_s",
    "sd_rt_s",         # sample SD (n - 1)
    "iqr_rt_s",
    "hu",              # Wagner's unbiased hit rate (emotion rows only)
    "kappa",           # Cohen's kappa (Total row only)
]


def _round(value: float | None, ndigits: int) -> float | str:
    """Round for CSV, or return '' for missing (so cells are empty, not 'None')."""
    return "" if value is None else float(round_half_up(value, ndigits))


def write_trials_csv(
    responses: Sequence[Response],
    path: str,
    *,
    flags: Sequence | None = None,
    rt_kind: str = DEFAULT_RT_KIND,
) -> str:
    """Write the per-trial CSV (one row per presentation); return the path."""
    if flags is None:
        _, flags = prepare_summary(responses, summary=None, rt_kind=rt_kind)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_TRIAL_FIELDS)
        writer.writeheader()
        for i, (r, flag) in enumerate(zip(responses, flags), start=1):
            writer.writerow({
                "trial": i,
                "audio_file": neutralize(r.stimulus.filename),
                "recording_id": neutralize(r.stimulus.recording_id),
                "true_emotion": r.true_emotion.label,
                "true_code": int(r.true_emotion),
                "chosen_emotion": r.responded.label if r.responded else "",
                "chosen_code": int(r.responded) if r.responded else "",
                "correct": int(r.is_correct) if r.answered else "",   # blank like chosen_*
                "rt_onset_s": _round(r.rt_onset, 4),
                "rt_offset_s": _round(r.rt_offset, 4),
                "replays": r.n_replays,
                "sex": r.sex.name.lower(),
                "rt_flag": RT_FLAG_LABEL[flag] or "ok",
                "background": neutralize(r.background),
                "pauses": r.n_pauses,
                "attempts": r.n_attempts,
                "choices": " > ".join(e.label for e in r.choices),
                "rt_speech_offset_s": _round(r.rt_speech_offset, 4),
            })
    return path


def _summary_row(group: str, stats: GroupStats, *, hu=None, kappa=None) -> dict:
    return {
        "group": group,
        "n_presented": stats.n_presented,
        "n_answered": stats.n_answered,
        "n_correct": stats.n_correct,
        "pct_correct": _round(stats.pct_correct, 2),
        "mean_rt_s": _round(stats.mean_rt, 4),
        "mean_replays": _round(stats.mean_replays, 3),
        "n_rt": stats.n_rt,
        "median_rt_s": _round(stats.median_rt, 4),
        "sd_rt_s": _round(stats.sd_rt, 4),
        "iqr_rt_s": _round(stats.iqr_rt, 4),
        "hu": _round(hu, 4),
        "kappa": _round(kappa, 4),
    }


def write_summary_csv(summary: SessionSummary, path: str) -> str:
    """Write the per-emotion / sex / total summary CSV; return the path."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_SUMMARY_FIELDS)
        writer.writeheader()
        for emo in summary.emotion_order:
            writer.writerow(_summary_row(emo.label, summary.per_emotion[emo],
                                         hu=summary.unbiased_hit_rate.get(emo)))
        for sex in SEXES_IN_ORDER:
            writer.writerow(_summary_row(sex.label, summary.per_sex[sex]))
        writer.writerow(_summary_row("Total", summary.total, kappa=summary.kappa))
    return path


def _with_suffix(path: str, suffix: str) -> str:
    """Insert *suffix* before the extension: 'x.csv' + '_summary' -> 'x_summary.csv'."""
    root, ext = os.path.splitext(path)
    return f"{root}{suffix}{ext or '.csv'}"


def write_csv_report(
    responses: Sequence[Response],
    path: str,
    *,
    summary: SessionSummary | None = None,
    rt_kind: str = DEFAULT_RT_KIND,
) -> list[str]:
    """Write both CSVs: per-trial at *path*, summary at '<path>_summary.csv'.

    Returns the two paths written, in that order.
    """
    summary, flags = prepare_summary(responses, summary=summary, rt_kind=rt_kind)
    trials_path = write_trials_csv(responses, path, flags=flags, rt_kind=rt_kind)
    summary_path = write_summary_csv(summary, _with_suffix(path, "_summary"))
    return [trials_path, summary_path]


def write_confusion_csv(
    responses: Sequence[Response],
    path: str,
    *,
    summary: SessionSummary | None = None,
    rt_kind: str = DEFAULT_RT_KIND,
) -> str:
    """Write the confusion matrix in long ("tidy") form; return the path.

    One row per (true emotion, chosen emotion) cell with its count and its share
    of the row -- ready for R/pandas without reshaping a 5x5 grid.
    """
    summary, _flags = prepare_summary(responses, summary=summary, rt_kind=rt_kind)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["true_emotion", "chosen_emotion", "count", "pct_of_row"])
        for i, true in enumerate(summary.emotion_order):
            for j, chosen in enumerate(summary.emotion_order):
                writer.writerow([true.label, chosen.label, summary.confusion[i][j],
                                 _round(summary.confusion_pct[i][j], 2)])
    return path
