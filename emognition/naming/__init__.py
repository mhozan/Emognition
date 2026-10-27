# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Stimulus naming + metadata: a BIDS-inspired scheme with legacy support.

The corpus is described two ways that stay in sync:

* **Filenames** -- canonical key-value "entities" (BIDS-style), e.g.
  ``speaker-01_emotion-happy_sex-f.wav``. Legacy ``..._EMO_G.wav`` names are still
  understood, and can be converted to canonical names. See :mod:`.entities`.
* **A sidecar manifest** -- ``stimuli.tsv`` (one row per file, editable in Excel)
  plus ``stimuli.json`` (a data dictionary: every column's meaning + allowed
  values). This is the source of truth, and the place rich/optional metadata
  (speaker, language, intensity, word, processing status, include flag, notes)
  lives. See :mod:`.manifest`.

This replaces brittle approaches like ID3/file tags: the manifest is structured,
validatable, Excel-editable, and travels with the folder.
"""

from .entities import (
    REQUIRED_ENTITIES,
    parse_any,
    parse_canonical,
    parse_entities,
    scan_stimuli,
    to_canonical_filename,
)
from .manifest import (
    DATA_DICTIONARY,
    MANIFEST_COLUMNS,
    RenameResult,
    StimulusRecord,
    apply_rename_plan,
    build_manifest,
    canonical_rename_plan,
    merge_manifest,
    read_manifest_tsv,
    validate_against_folder,
    write_data_dictionary,
    write_manifest,
)

__all__ = [
    # entities
    "REQUIRED_ENTITIES",
    "parse_entities",
    "parse_canonical",
    "parse_any",
    "scan_stimuli",
    "to_canonical_filename",
    # manifest
    "StimulusRecord",
    "MANIFEST_COLUMNS",
    "DATA_DICTIONARY",
    "build_manifest",
    "write_manifest",
    "read_manifest_tsv",
    "write_data_dictionary",
    "validate_against_folder",
    "canonical_rename_plan",
    "apply_rename_plan",
    "RenameResult",
    "merge_manifest",
]
