# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Calibrate a folder of recordings: loudness-normalize + trim silence.

A command-line front end for emognition.audio -- the same plan/confirm/apply flow
the Calibration UI (#9) will wrap in a dialog. Plays no audio; only reads and
writes files. Originals are never modified.

    python scripts/calibrate_audio.py                      # assets/audio -> assets/audio_calibrated
    python scripts/calibrate_audio.py IN --out OUT --method lufs --target -23
    python scripts/calibrate_audio.py IN --yes             # skip the confirmation
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from emognition.audio import NormalizationMethod, apply_plan, plan_batch  # noqa: E402
from emognition.audio.preprocess import DEFAULT_PAD_S  # noqa: E402


def _wavs(folder: str) -> list[str]:
    return sorted(
        os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".wav")
    )


def main(argv: list[str] | None = None) -> int:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description="Loudness-normalize + trim recordings")
    parser.add_argument("input", nargs="?", default=os.path.join(repo, "assets", "audio"),
                        help="folder of .wav recordings (default: assets/audio)")
    parser.add_argument("--out", default=None,
                        help="output folder (default: <input>_calibrated)")
    parser.add_argument("--method", choices=[m.value for m in NormalizationMethod],
                        default="lufs", help="loudness metric (default: lufs)")
    parser.add_argument("--target", type=float, default=None,
                        help="target level in the metric's dB units (default per method)")
    parser.add_argument("--pad-ms", type=float, default=DEFAULT_PAD_S * 1000.0,
                        help=f"padding kept around speech when trimming "
                             f"(default {DEFAULT_PAD_S * 1000:g} ms, same as the Calibration window)")
    parser.add_argument("--no-trim", action="store_true", help="don't trim silence")
    parser.add_argument("--no-normalize", action="store_true", help="don't change loudness")
    parser.add_argument("--yes", action="store_true", help="apply without confirmation")
    args = parser.parse_args(argv)

    paths = _wavs(args.input)
    if not paths:
        print(f"No .wav files in {args.input}", file=sys.stderr)
        return 1
    out_dir = args.out or (os.path.normpath(args.input) + "_calibrated")
    method = NormalizationMethod(args.method)

    plan = plan_batch(paths, out_dir, method=method, target_db=args.target,
                      pad_s=args.pad_ms / 1000.0)

    # Show the plan (this is the "confirmation" content).
    print(f"\nMethod: {method.value}  target: {plan.target_db:g} dB  "
          f"ceiling: {plan.ceiling_db:g} dBFS  pad: {args.pad_ms:g} ms")
    print(f"{'file':<18}{'dur→new (s)':>14}{'trim L/T (ms)':>16}"
          f"{'loud (dB)':>12}{'gain (dB)':>11}  flag")
    for c in plan.clips:
        flag = "PEAK-LIMITED" if c.will_limit else ""
        print(f"{c.filename:<18}{f'{c.orig_duration:.2f}→{c.new_duration:.2f}':>14}"
              f"{f'{c.lead_trim_s*1000:.0f}/{c.tail_trim_s*1000:.0f}':>16}"
              f"{c.measured_db:>12.1f}{c.gain_db:>11.1f}  {flag}")
    print(f"\nsummary: max trim {plan.max_trim_ms:.0f} ms | "
          f"max |gain| {plan.max_abs_gain_db:.1f} dB | "
          f"loudness spread {plan.loudness_spread_db:.1f} dB")
    if plan.is_minor():
        print("These files look already calibrated (changes are minor).")

    if not args.yes:
        reply = input(f"\nWrite {len(paths)} calibrated files to {out_dir}? [y/N] ")
        if reply.strip().lower() not in ("y", "yes"):
            print("Aborted; nothing written.")
            return 0

    try:
        written = apply_plan(plan, trim=not args.no_trim, normalize=not args.no_normalize)
    except ValueError as exc:     # output folder == input folder, or name collisions
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Wrote {len(written)} files to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
