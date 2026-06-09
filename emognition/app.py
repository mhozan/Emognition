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
import json as _json
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


def _psychopy_quit() -> None:
    # psychopy.core.quit() imports psychopy.iohub which needs pythoncom on
    # Windows; fall back to sys.exit so the process always exits cleanly.
    try:
        from psychopy import core
        core.quit()
    except (ImportError, ModuleNotFoundError):
        sys.exit(0)


def _run_session(args: argparse.Namespace) -> int:
    """Run a Test block from CLI settings, then write and open the reports.

    Settings come from the command line (not a GUI dialog) on purpose: opening a
    PyQt6 dialog and then a pyglet/OpenGL PsychoPy window in the *same* process
    crashes on Linux (the two toolkits fight over the GL context). The graphical
    setup screen (Phase 2, #12) will launch the experiment in a separate process
    to avoid exactly this. For now, defaults + flags keep things robust.
    """
    from .runtime import bootstrap

    bootstrap()

    from psychopy import core, visual

    from .core import SessionMode, build_trial_list
    from .io import open_path
    from .naming import scan_stimuli
    from .reports import (
        SessionInfo,
        write_csv_report,
        write_excel_report,
        write_html_report,
        write_pdf_report,
    )
    from .ui.assets import Caption, audio_dir
    from .ui.experiment_window import ExperimentAborted, TestExperiment

    audio_folder = args.audio_dir or audio_dir()
    stimuli = scan_stimuli(audio_folder)   # accepts canonical (BIDS) AND legacy names
    if not stimuli:
        print(f"No audio stimuli found in {audio_folder}.", file=sys.stderr)
        return 1
    emotions = _parse_emotions(args.emotions)
    trials = build_trial_list(stimuli, emotions=emotions, shuffle=not args.no_shuffle)

    started = datetime.now()
    win = visual.Window(
        size=(1280, 800), color=(-0.3, -0.3, -0.3), units="height",
        fullscr=args.fullscreen, screen=args.screen,
    )
    try:
        win.winHandle.set_caption("Emognition")  # title bar (windowed only)
    except Exception:
        pass
    mode = SessionMode(args.mode)
    experiment = TestExperiment(
        win,
        caption=Caption(_caption_value(args.caption)),
        emotions=emotions,
        allow_replays=args.allow_replays,
        amp_visualizer=args.amp_visualizer,
        volume=args.volume,
        mode=mode,
    )

    def _emit(data: dict) -> None:
        """Write a JSON status line to stdout for the experimenter monitor."""
        print(_json.dumps(data), flush=True)

    def _on_trial(response, index: int, total: int) -> None:
        if response is not None:
            _emit({
                "status": "trial",
                "index": index,
                "total": total,
                "emotion": response.true_emotion.name.lower(),
                "sex": response.sex.name.lower(),
                "responded": response.responded.name.lower() if response.responded else None,
                "correct": response.is_correct,
                "rt_ms": round(response.rt_offset * 1000) if response.rt_offset is not None else None,
            })
        else:
            # Passive training: clip was shown but no response collected.
            _emit({"status": "trial", "index": index, "total": total,
                   "responded": None, "correct": None, "rt_ms": None})

    _emit({"status": "start", "total": len(trials), "mode": args.mode,
           "participant": args.participant})
    aborted = False
    try:
        responses = experiment.run(trials, on_trial=_on_trial)
    except ExperimentAborted as abort:
        responses, aborted = getattr(abort, "partial", []), True
    finally:
        win.close()
    n_correct = sum(1 for r in responses if r.is_correct)
    _emit({"status": "done", "n_correct": n_correct, "n_trials": len(responses),
           "aborted": aborted})

    if not responses:
        if mode == SessionMode.PASSIVE_TRAINING:
            print(f"Passive training session complete ({len(trials)} clips presented).")
        else:
            print("No responses recorded.")
        _psychopy_quit()
        return 0

    save_dir = args.save_dir or _default_save_dir()
    os.makedirs(save_dir, exist_ok=True)
    stamp = started.strftime("%Y%m%d_%H%M%S")
    safe = "".join(c for c in args.participant if c.isalnum() or c in "-_") or "session"
    base = os.path.join(save_dir, f"{safe}_{stamp}")
    info = SessionInfo(
        participant=args.participant,
        experimenter=args.experimenter,
        mode=mode.label + (" (aborted)" if aborted else ""),
        audio_folder=audio_folder,
        started_at=started, finished_at=datetime.now(),
        app_version=__version__,
    )
    html = write_html_report(responses, base + ".html", info=info)
    write_excel_report(responses, base + ".xlsx", info=info)
    write_pdf_report(responses, base + ".pdf", info=info)
    write_csv_report(responses, base + ".csv")
    print(f"Reports saved to: {base}.(html|pdf|xlsx|csv)")
    open_path(html)

    _psychopy_quit()
    return 0


def _caption_value(choice: str) -> str:
    """Map a caption choice to the Caption enum value ('0'/'1'/'2')."""
    return {"english": "0", "mandarin": "1", "none": "2"}.get(choice, "2")


def _parse_emotions(spec: str | None):
    """Parse a comma-separated emotion-tag list into Emotions, or None for all."""
    if not spec:
        return None
    from .core import TAG_TO_EMOTION

    tags = [t.strip().lower() for t in spec.split(",") if t.strip()]
    emotions = [TAG_TO_EMOTION[t] for t in tags if t in TAG_TO_EMOTION]
    return emotions or None


def _open_config_ui() -> int:
    """Open the PyQt6 experimenter setup screen (the front door)."""
    from .ui.config_window import run_config_ui

    return run_config_ui()


def _open_calibration_ui() -> int:
    """Open the PyQt6 Calibration window."""
    from .ui.calibration_window import run_calibration_ui

    return run_calibration_ui()


def _play_tone(rms: float, seconds: float) -> int:
    """Play the SPL calibration tone, then exit (run as a subprocess, no window).

    Kept out of the Qt process on purpose; the Calibration window starts/stops
    this via QProcess so audio never shares the GUI process.
    """
    import tempfile

    import soundfile as sf

    from .runtime import bootstrap

    bootstrap()
    from psychopy import core, sound

    from .audio import calibration_tone

    rate = 44100
    tone = calibration_tone(rms, seconds, rate=rate)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        sf.write(fh.name, tone, rate)
        snd = sound.Sound(fh.name, stereo=False)
    snd.play()
    core.wait(seconds + 0.2)
    snd.stop()
    _psychopy_quit()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emognition", description="Speech Emotion Recognition")
    parser.add_argument("--version", action="version", version=f"Emognition {__version__}")
    parser.add_argument("--selfcheck", action="store_true",
                        help="import/initialise everything and exit (headless build test)")
    parser.add_argument("--setup", action="store_true",
                        help="open the experimenter setup screen (config UI)")
    parser.add_argument("--calibrate", action="store_true",
                        help="open the Calibration window (naming, loudness, SPL tone)")
    parser.add_argument("--play-tone", action="store_true",
                        help="play the SPL calibration tone and exit (used by the UI)")
    parser.add_argument("--tone-rms", type=float, default=0.05,
                        help="RMS amplitude of the calibration tone")
    parser.add_argument("--tone-seconds", type=float, default=60.0,
                        help="duration of the calibration tone (s)")
    parser.add_argument("--participant", default="Participant01",
                        help="participant label (default: Participant01)")
    parser.add_argument("--experimenter", default="APPstaff",
                        help="experimenter name (default: APPstaff)")
    parser.add_argument("--audio-dir", default=None,
                        help="folder of stimulus .wav files (default: bundled clips)")
    parser.add_argument("--emotions", default=None,
                        help="comma-separated emotion tags to test, e.g. hap,sad,ang "
                             "(default: all five)")
    parser.add_argument("--caption", choices=["none", "english", "mandarin"],
                        default="none", help="emoticon caption language (default: none)")
    parser.add_argument("--fullscreen", action="store_true",
                        help="run the experiment window full screen")
    parser.add_argument("--screen", type=int, default=0,
                        help="display index for the experiment window (default 0)")
    parser.add_argument("--no-shuffle", action="store_true",
                        help="present clips in folder order instead of shuffled")
    parser.add_argument("--allow-replays", action="store_true",
                        help="show a replay button (and 'r' key) to replay each clip")
    parser.add_argument("--amp-visualizer", action="store_true",
                        help="show a green amplitude LED during playback")
    parser.add_argument("--volume", type=float, default=0.8,
                        help="playback volume 0.0-1.0 (experimenter-set; default 0.8)")
    parser.add_argument("--save-dir", default=None,
                        help="folder for output reports (default: ./save_location)")
    parser.add_argument("--mode", choices=["test", "passive", "active"],
                        default="test",
                        help="session mode: test (default), passive training, "
                             "or active training with feedback")
    raw = sys.argv[1:] if argv is None else list(argv)
    args = parser.parse_args(raw)

    if args.selfcheck:
        return _selfcheck()
    if args.play_tone:
        return _play_tone(args.tone_rms, args.tone_seconds)
    if args.calibrate:
        return _open_calibration_ui()
    # Bare launch (no args) or explicit --setup opens the experimenter screen;
    # an explicit run (e.g. --participant ...) goes straight to the experiment.
    if args.setup or not raw:
        return _open_config_ui()
    return _run_session(args)


if __name__ == "__main__":
    raise SystemExit(main())
