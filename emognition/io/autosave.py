# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Crash-safe autosave: every finished trial is on disk the moment it ends.

Reports are written once, after the last trial; a crash, a power cut or a
closed window used to lose the whole session. While a session runs it now keeps
``<participant>_<stamp>.partial.jsonl`` (JSON Lines): a header line with what
is needed to carry on -- settings, seed and the full trial order -- then one
line per finished trial, flushed and fsync'ed. After the reports are written the
log is deleted; if it's still there, the session was interrupted and can be
resumed (``emognition --resume <log>``) with the same order, where it stopped.

JSON Lines because a crash can only ever tear the *last* line, which the reader
skips; every earlier line is complete and exact (no rounding, unlike a CSV).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import date, datetime

from ..config import CLEARED_DIR, session_file_pattern
from ..core.emotions import Emotion, Stimulus, TAG_TO_SEX
from ..core.responses import Response

PARTIAL_SUFFIX = ".partial.jsonl"
LOG_FORMAT = "emognition-session-log"
LOG_VERSION = 1


def _jsonable(value: object) -> str:
    """Timestamps as ISO 8601 (what ``datetime.fromisoformat`` reads back), else text."""
    return value.isoformat() if isinstance(value, (datetime, date)) else str(value)


def response_to_record(r: Response) -> dict:
    """One trial as plain JSON-able values (full precision)."""
    return {
        "file": r.stimulus.path,
        "emotion": int(r.true_emotion),
        "sex": r.sex.tag,
        "recording_id": r.stimulus.recording_id,
        "responded": None if r.responded is None else int(r.responded),
        "rt_onset": r.rt_onset,
        "rt_offset": r.rt_offset,
        "n_replays": r.n_replays,
        "background": r.background,
        "n_pauses": r.n_pauses,
        "choices": [int(e) for e in r.choices],
    }


def response_from_record(d: dict) -> Response:
    """Inverse of :func:`response_to_record`."""
    stim = Stimulus(path=d["file"], emotion=Emotion(d["emotion"]),
                    sex=TAG_TO_SEX[d["sex"]], recording_id=d.get("recording_id", ""))
    responded = d.get("responded")
    return Response(
        stimulus=stim,
        responded=None if responded is None else Emotion(responded),
        rt_onset=d.get("rt_onset"),
        rt_offset=d.get("rt_offset"),
        n_replays=int(d.get("n_replays", 0)),
        background=d.get("background", ""),
        n_pauses=int(d.get("n_pauses", 0)),
        choices=tuple(Emotion(c) for c in d.get("choices", ())),
    )


class SessionLog:
    """Append-only, crash-safe log of one session's trials."""

    def __init__(self, path: str, header: dict | None = None) -> None:
        """Start a new log with *header*, or (``header=None``) continue an existing one."""
        self.path = path
        self._fh = open(path, "a" if header is None else "x", encoding="utf-8")
        if header is not None:
            self._write({"format": LOG_FORMAT, "format_version": LOG_VERSION, **header})

    def _write(self, record: dict) -> None:
        self._fh.write(json.dumps(record, ensure_ascii=False, default=_jsonable) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())        # on disk now, not "eventually"

    def append(self, response: Response) -> None:
        self._write({"trial": response_to_record(response)})

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def discard(self) -> None:
        """Close and delete the log (call once the reports are safely written)."""
        self.close()
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass


def read_session_log(path: str) -> tuple[dict, list[Response]]:
    """Return (header, finished trials) from a log; a torn last line is skipped.

    Raises:
        ValueError: if the file isn't an Emognition session log.
    """
    header: dict | None = None
    responses: list[Response] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue                    # the line a crash interrupted
            if header is None:
                if record.get("format") != LOG_FORMAT:
                    raise ValueError(f"not an Emognition session log: {path}")
                header = record
            elif "trial" in record:
                responses.append(response_from_record(record["trial"]))
    if header is None:
        raise ValueError(f"empty session log: {path}")
    return header, responses


def clear_session(log_path: str) -> str:
    """Clear an unfinished session: move its log into ``cleared/`` beside it.

    It is then no longer offered for Resume, but nothing is lost: its trials
    stay in the file (move it back to resume it after all), and its participant
    ID still counts as used. Never overwrites: a taken name gets a number.
    Returns the new path.
    """
    folder = os.path.join(os.path.dirname(os.path.abspath(log_path)), CLEARED_DIR)
    os.makedirs(folder, exist_ok=True)
    name = os.path.basename(log_path)
    target, n = os.path.join(folder, name), 2
    while os.path.exists(target):
        target = os.path.join(folder, f"{name[: -len(PARTIAL_SUFFIX)]}-{n}{PARTIAL_SUFFIX}")
        n += 1
    os.replace(log_path, target)
    return target


def find_interrupted(folder: str, participant: str | None = None) -> list[str]:
    """Session logs left in *folder* (optionally only *participant*'s), newest first."""
    try:
        names: Iterable[str] = os.listdir(folder)
    except OSError:
        return []
    mine = session_file_pattern(participant, PARTIAL_SUFFIX) if participant is not None else None
    found = [
        os.path.join(folder, n) for n in names
        if n.endswith(PARTIAL_SUFFIX) and (mine is None or mine.fullmatch(n))
    ]
    return sorted(found, key=os.path.getmtime, reverse=True)

