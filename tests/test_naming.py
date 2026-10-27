# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Tests for the BIDS-inspired naming + manifest (filenames only, no audio)."""

import os

from emognition.core import Emotion, Sex
from emognition.naming import (
    build_manifest,
    canonical_rename_plan,
    parse_any,
    parse_canonical,
    read_manifest_tsv,
    scan_stimuli,
    to_canonical_filename,
    validate_against_folder,
    write_data_dictionary,
    write_manifest,
)


def _touch(folder, name):
    open(os.path.join(folder, name), "w").close()


# -- entities: canonical + legacy -----------------------------------------

def test_parse_canonical_full_entities():
    stim = parse_canonical("speaker-01_emotion-happy_sex-f_lang-en.wav")
    assert stim is not None
    assert stim.emotion is Emotion.HAPPY
    assert stim.sex is Sex.FEMALE
    assert stim.recording_id == "01"          # from the speaker entity


def test_parse_canonical_accepts_legacy_tag_and_unknown_sex():
    stim = parse_canonical("emotion-hap_sex-u.wav")   # 3-letter tag + unknown sex
    assert stim.emotion is Emotion.HAPPY
    assert stim.sex is Sex.UNKNOWN


def test_parse_canonical_requires_emotion_and_sex():
    assert parse_canonical("speaker-01_lang-en.wav") is None


def test_scan_stimuli_handles_canonical_and_legacy(tmp_path):
    _touch(tmp_path, "01_ang_f.wav")                       # legacy
    _touch(tmp_path, "speaker-02_emotion-happy_sex-m.wav")  # canonical (calibrated)
    _touch(tmp_path, "notes.wav")                           # unrecognized -> skipped
    found = scan_stimuli(str(tmp_path))
    assert len(found) == 2
    assert {s.emotion for s in found} == {Emotion.ANGRY, Emotion.HAPPY}


def test_parse_any_falls_back_to_legacy():
    stim = parse_any("01_ang_f.wav")          # legacy name, no entities
    assert stim is not None
    assert stim.emotion is Emotion.ANGRY and stim.sex is Sex.FEMALE
    assert stim.recording_id == "01"


def test_to_canonical_filename():
    name = to_canonical_filename(Emotion.ANGRY, Sex.FEMALE, speaker="03", language="en")
    assert name == "speaker-03_emotion-angry_sex-f_lang-en.wav"


# -- manifest --------------------------------------------------------------

def test_build_manifest_marks_unrecognized(tmp_path):
    _touch(tmp_path, "01_ang_f.wav")                       # legacy ok
    _touch(tmp_path, "speaker-02_emotion-happy_sex-m.wav")  # canonical ok
    _touch(tmp_path, "notes.wav")                           # unrecognized
    records = build_manifest(str(tmp_path))
    by_name = {r.filename: r for r in records}

    assert by_name["01_ang_f.wav"].emotion == "angry"
    assert by_name["speaker-02_emotion-happy_sex-m.wav"].speaker == "02"
    assert by_name["speaker-02_emotion-happy_sex-m.wav"].recognized
    assert not by_name["notes.wav"].recognized
    assert by_name["notes.wav"].include is False


def test_manifest_tsv_round_trip(tmp_path):
    _touch(tmp_path, "01_ang_f.wav")
    records = build_manifest(str(tmp_path))
    records[0].word = "hello"
    records[0].notes = "kept"
    path = write_manifest(records, str(tmp_path / "stimuli.tsv"))
    back = read_manifest_tsv(path)
    assert back[0].filename == "01_ang_f.wav"
    assert back[0].emotion == "angry" and back[0].sex == "f"
    assert back[0].word == "hello" and back[0].notes == "kept"


def test_validate_against_folder_flags_mismatches(tmp_path):
    _touch(tmp_path, "01_ang_f.wav")
    _touch(tmp_path, "02_hap_m.wav")
    records = build_manifest(str(tmp_path))
    os.remove(os.path.join(tmp_path, "02_hap_m.wav"))   # listed but now missing
    _touch(tmp_path, "03_sad_f.wav")                    # present but not listed
    missing, extra = validate_against_folder(records, str(tmp_path))
    assert missing == ["02_hap_m.wav"]
    assert extra == ["03_sad_f.wav"]


def test_canonical_rename_plan_only_changes_legacy(tmp_path):
    _touch(tmp_path, "01_ang_f.wav")                       # legacy -> needs rename
    _touch(tmp_path, "emotion-happy_sex-m.wav")            # already canonical
    records = build_manifest(str(tmp_path))
    plan = dict(canonical_rename_plan(records))
    # legacy '01_ang_f.wav': recording_id '01' becomes speaker entity
    assert plan["01_ang_f.wav"] == "speaker-01_emotion-angry_sex-f.wav"
    assert "emotion-happy_sex-m.wav" not in plan           # unchanged


def test_write_data_dictionary(tmp_path):
    path = write_data_dictionary(str(tmp_path / "stimuli.json"))
    import json
    spec = json.load(open(path, encoding="utf-8"))
    assert spec["sex"]["Levels"] == {"f": "Female", "m": "Male", "u": "Unknown"}
    assert "happy" in spec["emotion"]["Levels"]


# --- rename / manifest safety (Phase 3) -----------------------------------------

def _touch(folder, *names):
    for name in names:
        (folder / name).write_bytes(b"")


def test_legacy_prefixes_with_underscores_survive_renaming(tmp_path):
    from emognition.naming import apply_rename_plan, build_manifest, canonical_rename_plan, parse_any

    _touch(tmp_path, "subjectA_recording12_hap_f.wav", "subjectA_recording13_hap_f.wav")
    result = apply_rename_plan(str(tmp_path), canonical_rename_plan(build_manifest(str(tmp_path))))
    assert len(result.applied) == 2 and not result.skipped          # no collision
    ids = sorted(parse_any(str(tmp_path / new)).recording_id for _old, new in result.applied)
    assert ids == ["subjectA-recording12", "subjectA-recording13"]
    assert canonical_rename_plan(build_manifest(str(tmp_path))) == []   # idempotent


def test_take_and_unknown_entities_are_kept():
    from emognition.naming import StimulusRecord
    from emognition.naming.manifest import canonical_filename_for

    for name in ("speaker-01_emotion-happy_sex-f_take-2.wav",
                 "speaker-01_emotion-happy_sex-f_session-b.wav"):
        rec = StimulusRecord(filename=name, speaker="01", emotion="happy", sex="f")
        assert canonical_filename_for(rec) == name


def test_rename_reports_collisions_missing_and_unsafe_names(tmp_path):
    from emognition.naming import apply_rename_plan

    _touch(tmp_path, "a.wav", "taken.wav")
    result = apply_rename_plan(str(tmp_path), [
        ("a.wav", "taken.wav"),              # would overwrite
        ("gone.wav", "x.wav"),               # source missing
        ("../outside.wav", "y.wav"),         # not a bare name
        ("a.wav", "sub/z.wav"),              # not a bare name
    ])
    reasons = [why for _o, _n, why in result.skipped]
    assert result.applied == [] and len(reasons) == 4
    assert "already exists" in reasons[0] and "not found" in reasons[1]
    assert (tmp_path / "a.wav").exists() and (tmp_path / "taken.wav").exists()
    assert "Skipped 4" in result.summary()


def test_case_only_rename(tmp_path):
    from emognition.naming import apply_rename_plan

    _touch(tmp_path, "Clip_hap_f.wav")
    result = apply_rename_plan(str(tmp_path), [("Clip_hap_f.wav", "clip_hap_f.wav")])
    assert result.applied == [("Clip_hap_f.wav", "clip_hap_f.wav")]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["clip_hap_f.wav"]


def test_merge_keeps_hand_entered_columns_and_follows_renames():
    from emognition.naming import StimulusRecord, merge_manifest

    old = [StimulusRecord(filename="01_hap_f.wav", word="banana", notes="noisy", include=False)]
    fresh = [StimulusRecord(filename="speaker-01_emotion-happy_sex-f.wav", speaker="01",
                            emotion="happy", sex="f")]
    (merged,) = merge_manifest(fresh, old, renamed=[("01_hap_f.wav", "speaker-01_emotion-happy_sex-f.wav")])
    assert (merged.word, merged.notes, merged.include) == ("banana", "noisy", False)
    assert merged.emotion == "happy"                                   # parsed fields stay fresh


def test_manifest_reader_forgives_excel_edits(tmp_path):
    from emognition.naming import read_manifest_tsv

    path = tmp_path / "stimuli.tsv"
    text = "filename\temotion\tsex\tloudness_lufs\tnotes\n01_hap_f.wav\thappy\tf\t-23,5\n02_sad_m.wav\n"
    path.write_bytes(text.encode("utf-8-sig"))                         # BOM + short rows + comma
    first, second = read_manifest_tsv(str(path))
    assert first.filename == "01_hap_f.wav" and first.loudness_lufs == -23.5
    assert second.filename == "02_sad_m.wav" and second.notes == ""
