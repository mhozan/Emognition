# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Application entry point -- what the double-click executable runs.

For now this is a minimal launcher: a small setup dialog, a Test-mode block, and
report output. The full configuration screen lands in Phase 2 (#12); this gives
us something runnable to freeze and hand to colleagues today.

Two modes:
  * ``emognition``               run a session (GUI)
  * ``emognition --selfcheck``   import/initialise everything and exit 0
        -- a headless smoke test we run against the *frozen* binary to prove the
        PyInstaller bundle is complete, without needing a display.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from . import __version__


def _selfcheck() -> int:
    """Import the whole stack and initialise PsychoPy; print OK and exit.

    This is the headless gate for the packaged build: if a data file or hidden
    import is missing from the bundle, importing these will fail here instead of
    in front of a participant.
    """
    from .runtime import bootstrap

    bootstrap()
    # Importing these pulls in the audio/visual/keyboard backends + report deps.
    import psychtoolbox  # noqa: F401
    from psychopy import sound, visual  # noqa: F401
    from psychopy.hardware import keyboard  # noqa: F401

    from .core import scan_audio_dir  # noqa: F401
    from .reports import write_html_report  # noqa: F401
    from .ui.assets import audio_dir
    from .ui.experiment_window import TestExperiment  # noqa: F401

    n_clips = len([f for f in os.listdir(audio_dir()) if f.endswith(".wav")])
    print(f"Emognition {__version__} self-check OK "
          f"(python {sys.version.split()[0]}, {n_clips} bundled clips)")
    return 0


def _default_save_dir() -> str:
    """Where to write reports by default: a 'save_location' beside the app/cwd."""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.join(base, "save_location")


def _run_session(save_dir: str) -> int:
    """Show the setup dialog, run a Test block, write and open the reports."""
    from .runtime import bootstrap

    bootstrap()

    from psychopy import core, gui, visual

    from .core import build_trial_list, scan_audio_dir
    from .io import open_path
    from .reports import (
        SessionInfo,
        write_csv_report,
        write_excel_report,
        write_html_report,
    )
    from .ui.assets import Caption, audio_dir
    from .ui.experiment_window import ExperimentAborted, TestExperiment

    # --- minimal setup dialog (Qt-backed; no wxPython) --------------------
    fields = {
        "Participant": "Participant01",
        "Experimenter": "APPstaff",
        "Caption": ["none", "english", "mandarin"],
        "Fullscreen": False,
        "Shuffle": True,
    }
    dlg = gui.DlgFromDict(
        fields, title=f"Emognition {__version__}",
        order=["Participant", "Experimenter", "Caption", "Fullscreen", "Shuffle"],
    )
    if not dlg.OK:
        print("Cancelled.")
        return 0

    stimuli = scan_audio_dir(audio_dir())
    if not stimuli:
        print("No audio stimuli found.", file=sys.stderr)
        return 1
    trials = build_trial_list(stimuli, shuffle=bool(fields["Shuffle"]))

    started = datetime.now()
    win = visual.Window(
        size=(1280, 800), color=(-0.3, -0.3, -0.3), units="height",
        fullscr=bool(fields["Fullscreen"]),
    )
    experiment = TestExperiment(win, caption=Caption(_caption_value(fields["Caption"])))
    aborted = False
    try:
        responses = experiment.run(trials)
    except ExperimentAborted as abort:
        responses, aborted = getattr(abort, "partial", []), True
    finally:
        win.close()

    if not responses:
        print("No responses recorded.")
        core.quit()
        return 0

    os.makedirs(save_dir, exist_ok=True)
    stamp = started.strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in str(fields["Participant"]) if c.isalnum() or c in "-_") or "session"
    base = os.path.join(save_dir, f"{safe}_{stamp}")
    info = SessionInfo(
        participant=str(fields["Participant"]),
        experimenter=str(fields["Experimenter"]),
        mode="Test" + (" (aborted)" if aborted else ""),
        audio_folder=audio_dir(),
        started_at=started, finished_at=datetime.now(),
        app_version=__version__,
    )
    html = write_html_report(responses, base + ".html", info=info)
    write_excel_report(responses, base + ".xlsx", info=info)
    write_csv_report(responses, base + ".csv")
    print(f"Reports saved to: {base}.(html|xlsx|csv)")
    open_path(html)

    core.quit()
    return 0


def _caption_value(choice: str) -> str:
    """Map the dialog's caption label to the Caption enum value ('0'/'1'/'2')."""
    return {"english": "0", "mandarin": "1", "none": "2"}.get(choice, "2")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emognition", description="Speech Emotion Recognition")
    parser.add_argument("--version", action="version", version=f"Emognition {__version__}")
    parser.add_argument("--selfcheck", action="store_true",
                        help="import/initialise everything and exit (headless build test)")
    parser.add_argument("--save-dir", default=None,
                        help="folder for output reports (default: ./save_location)")
    args = parser.parse_args(argv)

    if args.selfcheck:
        return _selfcheck()
    return _run_session(args.save_dir or _default_save_dir())


if __name__ == "__main__":
    raise SystemExit(main())
