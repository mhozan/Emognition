# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Build / preview a stimulus manifest for a recording folder.

The command-line preview of the experimenter confirmation page (Calibration UI,
#9). Reads filenames only -- plays nothing, reads no audio.

    python scripts/stimuli_manifest.py [FOLDER]            # preview table + rename plan
    python scripts/stimuli_manifest.py FOLDER --write      # write stimuli.tsv + stimuli.json
    python scripts/stimuli_manifest.py FOLDER --rename --yes  # convert legacy names to canonical
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emognition.naming import (  # noqa: E402
    apply_rename_plan,
    build_manifest,
    canonical_rename_plan,
    merge_manifest,
    read_manifest_tsv,
    write_data_dictionary,
    write_manifest,
)


def main(argv: list[str] | None = None) -> int:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description="Build/preview a stimulus manifest")
    parser.add_argument("folder", nargs="?", default=os.path.join(repo, "assets", "audio"))
    parser.add_argument("--write", action="store_true",
                        help="write stimuli.tsv + stimuli.json into the folder")
    parser.add_argument("--rename", action="store_true",
                        help="convert legacy filenames to canonical BIDS-style names")
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    args = parser.parse_args(argv)

    records = build_manifest(args.folder)
    n_ok = sum(1 for r in records if r.recognized)
    print(f"\n{args.folder}  ({n_ok}/{len(records)} recognized)\n")
    print(f"  {'FILE':<34}{'SPEAKER':<9}{'EMOTION':<10}{'SEX':<5}STATUS")
    for r in records:
        print(f"  {r.filename:<34}{r.speaker:<9}{r.emotion or '?':<10}"
              f"{r.sex or '?':<5}{'ok' if r.recognized else 'UNRECOGNIZED'}")

    plan = canonical_rename_plan(records)
    if plan:
        print(f"\n  {len(plan)} file(s) would be renamed to canonical form:")
        for old, new in plan:
            print(f"    {old}  ->  {new}")

    if args.write:
        existing = os.path.join(args.folder, "stimuli.tsv")
        if os.path.exists(existing):        # keep what people typed into it
            records = merge_manifest(records, read_manifest_tsv(existing))
        tsv = write_manifest(records, existing)
        js = write_data_dictionary(os.path.join(args.folder, "stimuli.json"))
        print(f"\n  wrote {tsv}\n  wrote {js}")

    if args.rename and plan:
        if not args.yes:
            reply = input(f"\nRename {len(plan)} file(s) in place? [y/N] ")
            if reply.strip().lower() not in ("y", "yes"):
                print("Aborted; nothing renamed.")
                return 0
        result = apply_rename_plan(args.folder, plan)
        print(f"  {result.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
