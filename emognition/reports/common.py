# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Shared pieces for every report writer (Excel, PDF, HTML).

Keeping the session metadata and the "how do we render an empty/None value"
decisions in one place means the three report formats can't drift apart -- a
percent shown as ``75.0`` in the spreadsheet looks the same in the HTML and PDF.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from ..core import (
    Response,
    RtFlag,
    SessionSummary,
    flag_responses,
    scrub_flagged_rts,
    summarize,
)

# Labels for the three statistic columns, shared across all report formats.
STAT_COLUMNS: tuple[str, str, str] = ("% Correct", "Avg. Reaction (s)", "Avg. Replays")

# What to print where a statistic is undefined (e.g. an emotion never presented).
# An em dash reads as "no data", distinct from a real 0.
EMPTY = "—"  # —


@dataclass(slots=True)
class SessionInfo:
    """Human-facing metadata about one session, for the report headers.

    All fields are optional so a report can be generated from responses alone;
    the experiment/config layer fills these in when it has them.
    """

    participant: str = ""
    experimenter: str = ""
    mode: str = "Test"
    audio_folder: str = ""
    background: str = ""        # e.g. "Calm gradient" or "Slideshow: 6 pictures, ..."
    started_at: datetime | None = None    # when Begin was pressed (as in pb_beginner.m)
    finished_at: datetime | None = None
    rt_kind: str = "offset"
    app_version: str = ""
    notes: str = ""
    extra: dict[str, str] = field(default_factory=dict)


def fmt_pct(value: float | None) -> str:
    """Format a percentage to one decimal, or the empty marker if missing."""
    return EMPTY if value is None else f"{value:.1f}"


def fmt_seconds(value: float | None) -> str:
    """Format a reaction time in seconds to three decimals (ms resolution)."""
    return EMPTY if value is None else f"{value:.3f}"


def fmt_replays(value: float | None) -> str:
    """Format a mean replay count to two decimals."""
    return EMPTY if value is None else f"{value:.2f}"


def fmt_datetime(value: datetime | None) -> str:
    """Format a timestamp like '2026-06-08 14:30:05', or empty marker."""
    return EMPTY if value is None else value.strftime("%Y-%m-%d %H:%M:%S")


def fmt_duration(start: datetime | None, end: datetime | None) -> str:
    """Elapsed time as 'HH:MM:SS' (the original's monitorperf.m format), or empty marker."""
    if start is None or end is None:
        return EMPTY
    seconds = max(0, round((end - start).total_seconds()))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def info_rows(info: SessionInfo, rt_kind: str) -> list[tuple[str, str]]:
    """The session-details rows, in one order, for every report format.

    Each writer used to pick its own subset, so the PDF silently lacked the
    audio folder and app version. Values are strings; an empty value means
    "unknown" and each format renders it in its own way.
    """
    rows = [
        ("Participant", info.participant),
        ("Experimenter", info.experimenter),
        ("Mode", info.mode),
        ("Audio folder", info.audio_folder),
        ("Background", info.background),
        ("Started", fmt_datetime(info.started_at)),
        ("Finished", fmt_datetime(info.finished_at)),
        ("Duration", fmt_duration(info.started_at, info.finished_at)),
        ("Reaction-time basis", rt_kind),
        ("App version", info.app_version),
    ]
    rows.extend((str(k), str(v)) for k, v in info.extra.items())
    if info.notes:
        rows.append(("Notes", info.notes))
    return rows


# Short human labels for RT flags, shown in the per-trial tables.
RT_FLAG_LABEL: dict[RtFlag, str] = {
    RtFlag.OK: "",
    RtFlag.NO_RESPONSE: "no response",
    RtFlag.ANTICIPATORY: "anticipatory",
    RtFlag.SLOW_OUTLIER: "slow outlier",
}


def prepare_summary(
    responses: Sequence[Response],
    *,
    summary: SessionSummary | None,
    rt_kind: str,
    exclude_flagged: bool = True,
) -> tuple[SessionSummary, list[RtFlag]]:
    """Compute the RT flags and the summary the report should display.

    Every report writer calls this so they all treat flags identically:

    * Flags are computed for every trial (and shown per-trial in the report).
    * If ``summary`` isn't supplied, it's computed with flagged trials' RTs
      scrubbed (so reaction-time means ignore anticipatory/outlier trials) unless
      ``exclude_flagged`` is False. Accuracy/confusion are unaffected either way.

    Returns ``(summary, flags)`` with ``flags`` aligned to ``responses``.
    """
    flags = flag_responses(responses, rt_kind=rt_kind)
    if summary is None:
        source = scrub_flagged_rts(responses, flags) if exclude_flagged else list(responses)
        summary = summarize(source, rt_kind=rt_kind)
    return summary, flags
