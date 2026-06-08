# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Parsing and formatting BIDS-inspired stimulus filenames (legacy-compatible).

A **canonical** name is a chain of ``key-value`` entities joined by ``_``::

    speaker-01_emotion-happy_sex-f_lang-en_intensity-high.wav

Required entities: ``emotion`` and ``sex``. Recommended: ``speaker``. Optional:
``lang``, ``intensity``, ``take`` (and any others, preserved verbatim).

Emotion values are full words (happy/angry/neutral/sad/scared); the legacy
3-letter tags (hap/ang/...) are also accepted on input. Sex is ``f``/``m``/``u``
(or female/male/unknown). Anything that isn't a valid canonical name falls back
to the legacy ``..._EMO_G.wav`` parser, so old corpora keep working.
"""

from __future__ import annotations

import os

from ..core.emotions import Emotion, Sex, Stimulus, TAG_TO_EMOTION, TAG_TO_SEX
from ..core.stimuli import parse_stimulus_filename as _parse_legacy

# Entity keys we understand, in canonical filename order. Unknown keys are kept.
ENTITY_ORDER: tuple[str, ...] = ("speaker", "emotion", "sex", "lang", "intensity", "take")
REQUIRED_ENTITIES: tuple[str, ...] = ("emotion", "sex")

# emotion value -> Emotion: full words (canonical) plus the legacy 3-letter tags.
_EMOTION_VALUES: dict[str, Emotion] = {e.name.lower(): e for e in Emotion}
_EMOTION_VALUES.update(TAG_TO_EMOTION)  # "hap" etc. also accepted

# sex value -> Sex: 'f'/'m'/'u' plus full words.
_SEX_VALUES: dict[str, Sex] = dict(TAG_TO_SEX)
_SEX_VALUES.update({s.name.lower(): s for s in Sex})  # female/male/unknown


def parse_entities(filename: str) -> dict[str, str]:
    """Extract ``key-value`` entities from a filename's stem.

    Returns a dict of every ``key-value`` token found (e.g. ``{"emotion": "happy",
    "sex": "f"}``); empty if the name has no such tokens (e.g. a legacy name).
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    entities: dict[str, str] = {}
    for token in stem.split("_"):
        if "-" in token:
            key, value = token.split("-", 1)
            if key and value:
                entities[key.lower()] = value
    return entities


def parse_canonical(filename: str) -> Stimulus | None:
    """Parse a canonical BIDS-style name, or ``None`` if it isn't one.

    Requires valid ``emotion`` and ``sex`` entities. The ``recording_id`` is set
    to the ``speaker`` value if present, else the full filename stem.
    """
    entities = parse_entities(filename)
    emo_raw, sex_raw = entities.get("emotion"), entities.get("sex")
    if not emo_raw or not sex_raw:
        return None
    emotion = _EMOTION_VALUES.get(emo_raw.lower())
    sex = _SEX_VALUES.get(sex_raw.lower())
    if emotion is None or sex is None:
        return None
    stem = os.path.splitext(os.path.basename(filename))[0]
    recording_id = entities.get("speaker", stem)
    return Stimulus(path=filename, emotion=emotion, sex=sex, recording_id=recording_id)


def parse_any(filename: str) -> Stimulus | None:
    """Parse a canonical name, falling back to the legacy ``_EMO_G`` parser."""
    return parse_canonical(filename) or _parse_legacy(filename)


def to_canonical_filename(
    emotion: Emotion,
    sex: Sex,
    *,
    speaker: str | None = None,
    language: str | None = None,
    intensity: str | None = None,
    take: str | None = None,
    extension: str = ".wav",
) -> str:
    """Build a canonical filename from fields (full-word emotion, f/m/u sex)."""
    parts: list[str] = []
    if speaker:
        parts.append(f"speaker-{speaker}")
    parts.append(f"emotion-{emotion.name.lower()}")
    parts.append(f"sex-{sex.tag}")
    if language:
        parts.append(f"lang-{language}")
    if intensity:
        parts.append(f"intensity-{intensity}")
    if take:
        parts.append(f"take-{take}")
    return "_".join(parts) + extension
