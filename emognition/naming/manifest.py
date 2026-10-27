# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The stimulus manifest: ``stimuli.tsv`` (data) + ``stimuli.json`` (specs).

This is the source of truth for the corpus. ``stimuli.tsv`` has one row per audio
file and is edited in Excel; ``stimuli.json`` is the BIDS-style *data dictionary*
documenting every column (its meaning and allowed values), so the table is
self-describing and validatable.

Processing-status columns (``clipped``/``trimmed``/``normalized``/
``loudness_lufs``) are written by the calibration pipeline, so the manifest also
records what was done to each clip.
"""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass

from ..core.emotions import Emotion, Sex
from ..io.spreadsheet import neutralize, restore
from .entities import (
    _EMOTION_VALUES,
    _SEX_VALUES,
    parse_any,
    parse_canonical,
    parse_entities,
    to_canonical_filename,
)

MANIFEST_COLUMNS: tuple[str, ...] = (
    "filename", "recording_id", "speaker", "emotion", "sex", "language",
    "intensity", "word", "clipped", "trimmed", "normalized", "loudness_lufs",
    "include", "notes",
)

# BIDS-style data dictionary: every column's meaning and allowed values ("specs").
DATA_DICTIONARY: dict[str, dict] = {
    "filename": {"Description": "Audio file name within this folder."},
    "recording_id": {"Description": "Free-form recording identifier (legacy prefix "
                                    "or the speaker entity)."},
    "speaker": {"Description": "Speaker/actor identifier."},
    "emotion": {"Description": "Intended emotion of the recording.",
                "Levels": {e.name.lower(): e.label for e in Emotion}},
    "sex": {"Description": "Speaker sex.",
            "Levels": {"f": "Female", "m": "Male", "u": "Unknown"}},
    "language": {"Description": "Spoken language (e.g. en, zh)."},
    "intensity": {"Description": "Emotion intensity.",
                  "Levels": {"low": "low", "med": "medium", "high": "high"}},
    "word": {"Description": "Spoken word or sentence (transcript)."},
    "clipped": {"Description": "Peak clipping detected in the audio.", "Type": "boolean"},
    "trimmed": {"Description": "Leading/trailing silence has been trimmed.", "Type": "boolean"},
    "normalized": {"Description": "Loudness has been normalized.", "Type": "boolean"},
    "loudness_lufs": {"Description": "Measured integrated loudness.", "Units": "LUFS"},
    "include": {"Description": "Whether to include this clip in the experiment.",
                "Type": "boolean"},
    "notes": {"Description": "Free-text notes (e.g. why excluded)."},
}


def _b_out(value: bool | None) -> str:
    return "" if value is None else ("yes" if value else "no")


def _b_in(text: str) -> bool | None:
    t = text.strip().lower()
    if t in ("yes", "true", "1"):
        return True
    if t in ("no", "false", "0"):
        return False
    return None


@dataclass(slots=True)
class StimulusRecord:
    """One row of the manifest (one audio file + its metadata)."""

    filename: str
    recording_id: str = ""
    speaker: str = ""
    emotion: str = ""           # full word, e.g. "happy" (empty if unrecognized)
    sex: str = ""               # "f"/"m"/"u"
    language: str = ""
    intensity: str = ""
    word: str = ""
    clipped: bool | None = None
    trimmed: bool | None = None
    normalized: bool | None = None
    loudness_lufs: float | None = None
    include: bool = True
    notes: str = ""

    @property
    def recognized(self) -> bool:
        """True if emotion and sex are known (the file is usable as a stimulus)."""
        return bool(self.emotion) and bool(self.sex)

    def to_row(self) -> dict[str, str]:
        loud = "" if self.loudness_lufs is None else f"{self.loudness_lufs:.2f}"
        return {
            "filename": self.filename, "recording_id": self.recording_id,
            "speaker": self.speaker, "emotion": self.emotion, "sex": self.sex,
            "language": self.language, "intensity": self.intensity, "word": self.word,
            "clipped": _b_out(self.clipped), "trimmed": _b_out(self.trimmed),
            "normalized": _b_out(self.normalized), "loudness_lufs": loud,
            "include": _b_out(self.include), "notes": self.notes,
        }

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "StimulusRecord":
        loud = row.get("loudness_lufs", "").strip()
        return cls(
            filename=row.get("filename", ""),
            recording_id=row.get("recording_id", ""),
            speaker=row.get("speaker", ""),
            emotion=row.get("emotion", ""),
            sex=row.get("sex", ""),
            language=row.get("language", ""),
            intensity=row.get("intensity", ""),
            word=row.get("word", ""),
            clipped=_b_in(row.get("clipped", "")),
            trimmed=_b_in(row.get("trimmed", "")),
            normalized=_b_in(row.get("normalized", "")),
            loudness_lufs=float(loud) if loud else None,
            include=_b_in(row.get("include", "")) is not False,  # default include
            notes=row.get("notes", ""),
        )


def _record_from_filename(directory: str, name: str) -> StimulusRecord:
    """Build a record by parsing one filename (canonical or legacy)."""
    path = os.path.join(directory, name)
    stim = parse_any(path)
    if stim is None:
        return StimulusRecord(
            filename=name, include=False,
            notes="UNRECOGNIZED name; rename to <id>_<EMO>_<SEX>.wav to include.",
        )
    entities = parse_entities(name)
    is_canonical = parse_canonical(path) is not None
    if "speaker" in entities:
        speaker = entities["speaker"]
    elif not is_canonical:
        # Legacy name: keep its prefix as the speaker id so the canonical rename
        # stays unique (e.g. "01_ang_f.wav" -> "speaker-01_emotion-angry_sex-f.wav").
        speaker = stim.recording_id
    else:
        speaker = ""  # canonical name that simply omits a speaker entity
    return StimulusRecord(
        filename=name,
        recording_id=stim.recording_id,
        speaker=speaker,
        emotion=stim.emotion.name.lower(),
        sex=stim.sex.tag,
        language=entities.get("lang", ""),
        intensity=entities.get("intensity", ""),
    )


def build_manifest(directory: str, *, extensions: tuple[str, ...] = (".wav",)) -> list[StimulusRecord]:
    """Bootstrap a manifest by parsing every audio filename in *directory*."""
    exts = tuple(e.lower() for e in extensions)
    names = sorted(f for f in os.listdir(directory) if f.lower().endswith(exts))
    return [_record_from_filename(directory, n) for n in names]


def write_manifest(records: Sequence[StimulusRecord], path: str) -> str:
    """Write records to a TSV manifest; return the path."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(MANIFEST_COLUMNS), delimiter="\t")
        writer.writeheader()
        for rec in records:
            # The TSV is meant to be edited in a spreadsheet: keep file names inert.
            writer.writerow({k: neutralize(v) for k, v in rec.to_row().items()})
    return path


def read_manifest_tsv(path: str) -> list[StimulusRecord]:
    """Read a TSV manifest back into records."""
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            StimulusRecord.from_row({k: restore(v) if isinstance(v, str) else v for k, v in row.items()})
            for row in csv.DictReader(fh, delimiter="\t")
        ]


def write_data_dictionary(path: str) -> str:
    """Write the JSON data dictionary (column specs); return the path."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(DATA_DICTIONARY, fh, indent=2)
        fh.write("\n")
    return path


def validate_against_folder(
    records: Sequence[StimulusRecord], directory: str,
    *, extensions: tuple[str, ...] = (".wav",),
) -> tuple[list[str], list[str]]:
    """Reconcile manifest vs disk. Returns (missing_files, files_not_in_manifest)."""
    exts = tuple(e.lower() for e in extensions)
    on_disk = {f for f in os.listdir(directory) if f.lower().endswith(exts)}
    in_manifest = {r.filename for r in records}
    missing = sorted(in_manifest - on_disk)       # listed but not present
    extra = sorted(on_disk - in_manifest)          # present but not listed
    return missing, extra


def canonical_filename_for(record: StimulusRecord) -> str | None:
    """The canonical BIDS-style name for a record, or None if unrecognized."""
    emotion = _EMOTION_VALUES.get(record.emotion.lower())
    sex = _SEX_VALUES.get(record.sex.lower())
    if emotion is None or sex is None:
        return None
    ext = os.path.splitext(record.filename)[1] or ".wav"
    return to_canonical_filename(
        emotion, sex,
        speaker=record.speaker or None,
        language=record.language or None,
        intensity=record.intensity or None,
        extension=ext,
    )


def canonical_rename_plan(records: Sequence[StimulusRecord]) -> list[tuple[str, str]]:
    """Return (old_name, new_name) pairs to convert recognized files to canonical.

    Files already in canonical form (or unrecognized) are skipped.
    """
    plan: list[tuple[str, str]] = []
    for rec in records:
        canonical = canonical_filename_for(rec)
        if canonical and canonical != rec.filename:
            plan.append((rec.filename, canonical))
    return plan


def apply_rename_plan(directory: str, plan: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    """Apply a rename plan on disk; return the pairs actually renamed.

    Refuses to overwrite an existing target (skips that pair) so no file is ever
    clobbered. Returns the pairs that were renamed.
    """
    applied: list[tuple[str, str]] = []
    for old, new in plan:
        src, dst = os.path.join(directory, old), os.path.join(directory, new)
        if not os.path.exists(src) or os.path.exists(dst):
            continue  # source gone or target would be overwritten -> skip safely
        os.rename(src, dst)
        applied.append((old, new))
    return applied
