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

# Entities that map onto manifest columns (everything else is carried verbatim).
_COLUMN_ENTITIES = frozenset({"speaker", "emotion", "sex", "lang", "intensity"})

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


def _float_in(text: str) -> float | None:
    try:
        return float(text.replace(",", ".")) if text else None
    except ValueError:
        return None


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
    def from_row(cls, row: dict[str, str | None]) -> "StimulusRecord":
        """Build a record from a TSV row, forgiving hand edits.

        Short rows (missing cells come back as ``None``), surrounding spaces and a
        decimal comma (``-23,5``, as some spreadsheets save) are all accepted; an
        unreadable loudness value is treated as unknown rather than crashing.
        """
        def cell(key: str) -> str:
            return (row.get(key) or "").strip()

        return cls(
            filename=cell("filename"),
            recording_id=cell("recording_id"),
            speaker=cell("speaker"),
            emotion=cell("emotion"),
            sex=cell("sex"),
            language=cell("language"),
            intensity=cell("intensity"),
            word=cell("word"),
            clipped=_b_in(cell("clipped")),
            trimmed=_b_in(cell("trimmed")),
            normalized=_b_in(cell("normalized")),
            loudness_lufs=_float_in(cell("loudness_lufs")),
            include=_b_in(cell("include")) is not False,  # default include
            notes=cell("notes"),
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
    """Read a TSV manifest back into records.

    ``utf-8-sig`` because Excel adds a byte-order mark when it saves UTF-8: read
    as plain UTF-8, the BOM became part of the first header ("\ufefffilename")
    and every filename came back empty.
    """
    with open(path, newline="", encoding="utf-8-sig") as fh:
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
    # A canonical name may carry entities the record has no column for (take-2,
    # session-b, ...): keep them, or two takes would collapse onto one name.
    take, extra = None, {}
    if parse_canonical(record.filename) is not None:
        for key, value in parse_entities(record.filename).items():
            if key == "take":
                take = value
            elif key not in _COLUMN_ENTITIES:
                extra[key] = value
    return to_canonical_filename(
        emotion, sex,
        speaker=record.speaker or None,
        language=record.language or None,
        intensity=record.intensity or None,
        take=take,
        extra=extra,
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


@dataclass(frozen=True, slots=True)
class RenameResult:
    """What a rename pass did: the pairs renamed, and every skip with its reason."""

    applied: list[tuple[str, str]]
    skipped: list[tuple[str, str, str]]      # (old, new, reason)

    def summary(self) -> str:
        text = f"Renamed {len(self.applied)} file(s)."
        if self.skipped:
            reasons = "; ".join(f"{old}: {why}" for old, _new, why in self.skipped[:5])
            more = f" (+{len(self.skipped) - 5} more)" if len(self.skipped) > 5 else ""
            text += f" Skipped {len(self.skipped)}: {reasons}{more}"
        return text


def _bare_name(name: str) -> bool:
    """True for a plain file name (no folder parts, not '.'/'..')."""
    return bool(name) and name not in (".", "..") and os.path.basename(name) == name \
        and not any(sep and sep in name for sep in (os.sep, os.altsep, "/", "\\"))


def apply_rename_plan(directory: str, plan: Sequence[tuple[str, str]]) -> RenameResult:
    """Apply a rename plan inside *directory*; never overwrite, never leave it.

    * Only bare file names are accepted -- a plan read from an edited manifest
      can't move files in or out of the folder.
    * An existing target is never overwritten (reported as a collision).
    * A change of letter case only (``A.wav`` -> ``a.wav``) goes through a
      temporary name, because on Windows/macOS the target "already exists".
    * One failing rename doesn't stop the rest; everything is reported.
    """
    applied: list[tuple[str, str]] = []
    skipped: list[tuple[str, str, str]] = []
    for old, new in plan:
        if not (_bare_name(old) and _bare_name(new)):
            skipped.append((old, new, "not a plain file name"))
            continue
        src, dst = os.path.join(directory, old), os.path.join(directory, new)
        if not os.path.exists(src):
            skipped.append((old, new, "file not found"))
            continue
        case_only = old != new and os.path.normcase(old) == os.path.normcase(new) or (
            old != new and os.path.exists(dst) and os.path.samefile(src, dst)
        )
        if os.path.exists(dst) and not case_only:
            skipped.append((old, new, f"{new} already exists"))
            continue
        try:
            if case_only:
                tmp = src + ".renaming"
                os.rename(src, tmp)
                os.rename(tmp, dst)
            else:
                os.rename(src, dst)
        except OSError as exc:
            skipped.append((old, new, str(exc)))
            continue
        applied.append((old, new))
    return RenameResult(applied=applied, skipped=skipped)


def merge_manifest(
    fresh: Sequence[StimulusRecord],
    existing: Sequence[StimulusRecord],
    *,
    renamed: Sequence[tuple[str, str]] = (),
) -> list[StimulusRecord]:
    """Combine freshly parsed records with an existing (hand-edited) manifest.

    Fields that come from the file name (emotion, sex, speaker, ...) are taken
    from *fresh*; what people typed (word, notes, include, processing flags,
    loudness) is kept from *existing* -- rebuilding stimuli.tsv used to wipe it.
    *renamed* (old, new) pairs let a row follow its file to a new name.
    """
    new_name = dict(renamed)
    kept = {new_name.get(r.filename, r.filename): r for r in existing}
    merged: list[StimulusRecord] = []
    for rec in fresh:
        old = kept.get(rec.filename)
        if old is not None:
            rec.word, rec.notes, rec.include = old.word, old.notes, old.include
            rec.clipped, rec.trimmed, rec.normalized = old.clipped, old.trimmed, old.normalized
            rec.loudness_lufs = old.loudness_lufs
            rec.language = rec.language or old.language
            rec.intensity = rec.intensity or old.intensity
        merged.append(rec)
    return merged
