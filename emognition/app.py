# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Application entry point -- what the double-click executable runs.

Started with no arguments it opens the experimenter setup window; given session
options (``--participant ...``) it runs one session in this process and writes
the reports. The setup window launches sessions exactly that way, as a separate
process, because a Qt window and the PsychoPy window must never share one.

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
import random
import secrets
import sys
import tempfile
from datetime import datetime
from typing import NoReturn

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
    from psychopy import sound, visual  # noqa: F401  (visual: import check only)
    from psychopy.hardware import keyboard  # noqa: F401

    from .core import scan_audio_dir  # noqa: F401
    from .core.backgrounds import CALM_GRADIENT, list_pictures
    from .imaging import render_background
    from .reports import write_html_report  # noqa: F401
    from .ui.assets import audio_dir, backgrounds_dir
    from .ui.experiment_window import TestExperiment  # noqa: F401

    # The audio engine the RTs depend on must load from the bundle: PsychoPy would
    # otherwise fall back quietly, and PsychPortAudio failing to load is exactly
    # what broke an arm64 macOS build once.
    backend = sound.Sound.resolveBackend().__name__
    if backend != "psychopy.sound.backend_ptb":
        raise RuntimeError(f"audio backend is {backend}, not PsychToolbox")
    n_clips = len([f for f in os.listdir(audio_dir()) if f.endswith(".wav")])
    pictures = list_pictures(backgrounds_dir())
    # Decode the default and one bundled picture: proves Pillow's codecs are bundled.
    for source in [CALM_GRADIENT, *pictures[:1]]:
        _image, problem = render_background(source, (64, 36))
        if problem:
            raise RuntimeError(problem)
    print(f"Emognition {__version__} self-check OK "
          f"(python {sys.version.split()[0]}, PTB audio, {n_clips} bundled clips, "
          f"{len(pictures)} background pictures)")
    return 0


def _psychopy_quit(code: int = 0) -> NoReturn:
    """Shut PsychoPy down cleanly, then exit with *code*.

    ``psychopy.core.quit()`` tidies up (audio streams, windows) and then calls
    ``sys.exit(0)`` itself, which would hide a failure from the setup window; we
    catch that exit and use our own code. It also imports psychopy.iohub, which
    needs pythoncom on Windows -- if that import fails we simply exit.
    """
    try:
        from psychopy import core
        core.quit()
    except SystemExit:
        pass
    except (ImportError, ModuleNotFoundError):
        pass
    sys.exit(code)


def _use_utf8_output() -> None:
    """Make stdout/stderr UTF-8 so printing never fails on a participant's name.

    A piped stdout on Windows defaults to the ANSI code page with strict errors:
    printing "José" or a Mandarin caption could raise *after* the session. The
    setup window decodes the pipe as UTF-8.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass   # not a reconfigurable text stream (e.g. None in a windowed build)


def _emit(data: dict) -> None:
    """Write one JSON status line to stdout for the experimenter monitor.

    Never raises: if the setup window has gone away (a broken pipe), the session
    -- and above all its reports -- must carry on regardless.
    """
    try:
        print(_json.dumps(data), flush=True)
    except (OSError, ValueError):
        pass


def _prepare_save_dir(path: str) -> str:
    """Create the report folder and prove it is writable -- before, not after, the session."""
    os.makedirs(path, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path, prefix=".emognition-write-test-"):
        pass
    return path


def _report_base(save_dir: str, participant: str, started: datetime) -> str:
    """'<save_dir>/<participant>_<YYYYmmdd_HHMMSS>' (participant reduced to safe characters)."""
    from .config import participant_file_stem

    stem = participant_file_stem(participant)
    return os.path.join(save_dir, f"{stem}_{started.strftime('%Y%m%d_%H%M%S')}")


def _safe_timing(experiment) -> dict:
    """The experiment's timing QA, or {} -- QA must never cost the session's data."""
    try:
        return experiment.timing_summary()
    except Exception as exc:  # noqa: BLE001
        print(f"Timing summary unavailable: {exc!r}", file=sys.stderr)
        return {}


def _timing_rows(seed: int, timing: dict) -> dict[str, str]:
    """Session-details rows for the reports: the seed and the timing quality."""
    rows = {"Random seed": str(seed)}
    hz = timing.get("refresh_hz")
    if hz:
        rows["Refresh rate"] = f"{hz:.1f} Hz" + ("" if timing.get("refresh_measured") else " (assumed)")
    recorded = timing.get("frames_recorded")
    if recorded:
        dropped = timing.get("frames_dropped", 0)
        rows["Dropped frames"] = f"{dropped} of {recorded:,} ({100.0 * dropped / recorded:.2f}%)"
    latency = timing.get("audio_predicted_latency_ms")
    if latency is not None:
        rows["Audio latency (predicted)"] = f"{latency:.1f} ms"
    return rows


def _write_reports(responses, base: str, info, record: dict | None = None) -> tuple[str | None, list[str]]:
    """Write every report format; return (HTML path or None, formats that failed).

    The raw per-trial CSV goes first, then the JSON sidecar (*record*: how the
    session was run), so the data is on disk before anything fancier is
    attempted; each format is isolated, so a plotting or font problem in the
    PDF can't take the others (or the data) with it.
    """
    from .reports import (
        write_confusion_csv,
        write_csv_report,
        write_excel_report,
        write_html_report,
        write_pdf_report,
    )
    from .reports.sidecar import write_session_sidecar

    writers = (
        ("CSV", lambda: write_csv_report(responses, base + ".csv")),
        ("JSON", lambda: write_session_sidecar(base + ".json", record or {})),
        ("confusion CSV", lambda: write_confusion_csv(responses, base + "_confusion.csv")),
        ("Excel", lambda: write_excel_report(responses, base + ".xlsx", info=info)),
        ("HTML", lambda: write_html_report(responses, base + ".html", info=info)),
        ("PDF", lambda: write_pdf_report(responses, base + ".pdf", info=info)),
    )
    html, failed = None, []
    for name, write in writers:
        try:
            written = write()
        except Exception as exc:  # noqa: BLE001 -- one failing format must not lose the rest
            failed.append(name)
            print(f"Could not write the {name} report: {exc!r}", file=sys.stderr)
            continue
        if name == "HTML":
            html = written
    return html, failed


# Settings a resumed session takes from its log, except these (the display can
# differ, and the log itself is what's being resumed).
_RESUME_KEEP = frozenset({"resume", "screen", "fullscreen", "no_begin"})


def _apply_saved_settings(args: argparse.Namespace, saved: dict) -> None:
    """Resume with the interrupted session's own settings (participant, mode, ...)."""
    for key, value in saved.items():
        if key not in _RESUME_KEEP and hasattr(args, key):
            setattr(args, key, value)


def _stimuli_from_paths(paths: list[str], audio_folder: str):
    """The interrupted session's trial order, re-parsed from its saved file paths.

    A clip that's no longer at its saved path (the app was moved or updated in
    between) is looked up by name in *audio_folder*: the name is what says which
    emotion and voice it is.

    Raises:
        ValueError: naming a clip that can't be found either way.
    """
    from .naming import parse_any

    stimuli = []
    for path in paths:
        if not os.path.exists(path):
            path = os.path.join(audio_folder, os.path.basename(path))
        stim = parse_any(path) if os.path.exists(path) else None
        if stim is None:
            raise ValueError(f"Cannot resume: stimulus missing or renamed: {path}")
        stimuli.append(stim)
    return stimuli


def _open_session_log(path: str, header: dict | None):
    """Start (or, with header=None, continue) the autosave log; None if impossible."""
    from .io.autosave import SessionLog

    try:
        return SessionLog(path, header)
    except OSError as exc:
        print(f"Autosave unavailable ({exc}); trials are only saved at the end.", file=sys.stderr)
        return None


def _run_session(args: argparse.Namespace) -> int:
    """Run a session from CLI settings, then write and open the reports.

    Settings come from the command line (not a GUI dialog) on purpose: opening a
    PyQt6 dialog and then a pyglet/OpenGL PsychoPy window in the *same* process
    crashes on Linux (the two toolkits fight over the GL context). The setup
    window therefore launches this in a separate process.

    Every finished trial is autosaved to ``<base>.partial.jsonl``; with
    ``--resume <that file>`` an interrupted session carries on with the same
    trial order and settings, and its reports cover all of its trials.

    Exit codes: 0 done; 1 nothing to run or nowhere to save; 2 a bad setting;
    3 the session ran but a report format could not be written (see stderr --
    the CSV is written first, so the raw data is normally still safe).
    """
    _use_utf8_output()
    resume_header, done = None, []
    if args.resume:
        from .io.autosave import read_session_log

        try:
            resume_header, done = read_session_log(args.resume)
        except (OSError, ValueError) as exc:
            print(f"Cannot resume {args.resume}: {exc}", file=sys.stderr)
            return 2
        _apply_saved_settings(args, resume_header.get("settings", {}))
    try:
        emotions = _parse_emotions(args.emotions)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    from .runtime import bootstrap

    bootstrap()

    from psychopy import visual

    from .core import SessionMode, build_trial_list
    from .core.backgrounds import resolve_background
    from .io.autosave import PARTIAL_SUFFIX
    from .naming import scan_stimuli
    from .ui.assets import Caption, audio_dir, background_folders, default_save_dir
    from .ui.experiment_window import ExperimentAborted, TestExperiment

    audio_folder = args.audio_dir or audio_dir()
    if resume_header:
        seed = int(resume_header["random_seed"])
        try:
            trials = _stimuli_from_paths(resume_header["trial_order"], audio_folder)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    else:
        stimuli = scan_stimuli(audio_folder)   # accepts canonical (BIDS) AND legacy names
        if not stimuli:
            print(f"No audio stimuli found in {audio_folder}.", file=sys.stderr)
            return 1
        # One recorded seed drives every random choice, so a session's order can be
        # reproduced exactly (--seed) -- the original never seeded its RNG at all,
        # so the first session after each launch always got the same order.
        seed = args.seed if args.seed is not None else secrets.randbelow(2**31 - 1)
        trials = build_trial_list(stimuli, emotions=emotions, shuffle=not args.no_shuffle,
                                  rng=random.Random(seed))
    if not trials:
        chosen = ", ".join(e.label for e in emotions) if emotions else "the selected emotions"
        print(f"No clips in {audio_folder} match {chosen}; nothing to present.", file=sys.stderr)
        return 1
    remaining = trials[len(done):]
    try:
        plan = resolve_background(
            args.background, picture_folders=background_folders(),
            every_n=args.background_every, shuffle=args.background_shuffle,
            rng=random.Random(seed + 1),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    save_dir = args.save_dir or default_save_dir()
    try:
        _prepare_save_dir(save_dir)
    except OSError as exc:
        print(f"Cannot save reports in {save_dir}: {exc}", file=sys.stderr)
        return 1

    mode = SessionMode(args.mode)
    launched = datetime.now()
    log = None
    aborted = False
    begun_at: datetime | None = None
    new_responses = []
    timing: dict = {}

    def _on_trial(response, index: int, total: int) -> None:
        nonlocal log
        if response is not None:
            if log is not None:
                try:
                    log.append(response)        # on disk before the next clip starts
                except OSError as exc:          # e.g. disk full: warn once, carry on
                    print(f"Autosave stopped ({exc}); the remaining trials are saved "
                          "with the reports at the end.", file=sys.stderr)
                    log.close()
                    log = None
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

    if remaining:
        win = visual.Window(
            size=(1280, 800), color=(-0.3, -0.3, -0.3), units="height",
            fullscr=args.fullscreen, screen=args.screen,
        )
        try:
            win.winHandle.set_caption("Emognition")  # title bar (windowed only)
        except Exception:
            pass
        experiment = TestExperiment(
            win,
            caption=Caption(_caption_value(args.caption)),
            emotions=emotions,
            allow_replays=args.allow_replays,
            amp_visualizer=args.amp_visualizer,
            volume=args.volume,
            mode=mode,
            background=plan,
            first_trial=len(done) + 1,
        )
        # A resumed session tells the monitor what's already done, so its trial
        # counter and running accuracy carry on instead of restarting at zero.
        _emit({"status": "start", "total": len(trials), "mode": args.mode,
               "participant": args.participant, "done": len(done),
               "n_correct": sum(1 for r in done if r.is_correct),
               "n_answered": sum(1 for r in done if r.answered)})
        try:
            experiment.prepare(remaining)        # audio stream, pictures, GPU warm-up
            if args.no_begin:
                begun_at = datetime.now()
            else:
                _emit({"status": "waiting"})
                begun_at = experiment.wait_for_begin()
            _emit({"status": "begun", "total": len(trials), "done": len(done)})
            if mode != SessionMode.PASSIVE_TRAINING:   # passive training records nothing
                if resume_header:
                    log = _open_session_log(args.resume, None)
                else:
                    base = _report_base(save_dir, args.participant, begun_at)
                    log = _open_session_log(base + PARTIAL_SUFFIX, {
                        "app_version": __version__,
                        "participant": args.participant,
                        "experimenter": args.experimenter,
                        "started_at": begun_at,
                        "base": base,
                        "random_seed": seed,
                        "settings": dict(vars(args)),
                        "audio_folder": audio_folder,
                        # Absolute, so a resume started from another folder finds them.
                        "trial_order": [os.path.abspath(t.path) for t in trials],
                    })
            new_responses = experiment.run(remaining, on_trial=_on_trial)
        except ExperimentAborted as abort:
            new_responses, aborted = getattr(abort, "partial", []), True
        finally:
            timing = _safe_timing(experiment)
            experiment.close()
            win.close()
            if log is not None:
                log.close()
    responses = [*done, *new_responses]
    finished_at = datetime.now()
    n_correct = sum(1 for r in responses if r.is_correct)
    n_answered = sum(1 for r in responses if r.answered)
    _emit({"status": "done", "n_correct": n_correct, "n_trials": len(responses),
           "n_answered": n_answered, "aborted": aborted})

    if not responses:
        if log is not None:
            log.discard()                       # nothing to resume
        if mode == SessionMode.PASSIVE_TRAINING:
            print(f"Passive training session complete ({len(trials)} clips presented).")
        else:
            print("No responses recorded.")
        _psychopy_quit(0)

    # Report writers (openpyxl, fpdf2, matplotlib: ~0.5 s of imports) load only
    # now, after the window has closed, instead of delaying the window opening.
    from .io import open_path
    from .reports import SessionInfo
    from .reports.sidecar import environment_info

    if resume_header:
        started = datetime.fromisoformat(str(resume_header["started_at"]))
        base = resume_header["base"]            # the reports keep the original name
    else:
        started = begun_at or launched          # the session starts when Begin is pressed
        base = _report_base(save_dir, args.participant, started)
    label = mode.label + (" (resumed)" if resume_header else "") + (" (aborted)" if aborted else "")
    info = SessionInfo(
        participant=args.participant,
        experimenter=args.experimenter,
        mode=label,
        audio_folder=audio_folder,
        background=plan.describe(),
        started_at=started, finished_at=finished_at,
        app_version=__version__,
        extra=_timing_rows(seed, timing),
    )
    record = {
        "app_version": __version__,
        "participant": args.participant,
        "experimenter": args.experimenter,
        "mode": args.mode,
        "aborted": aborted,
        "resumed_from": args.resume,
        "n_trials_before_resume": len(done),
        "launched_at": launched,
        "started_at": started,
        "finished_at": finished_at,
        "random_seed": seed,
        "settings": dict(vars(args)),
        "audio_folder": audio_folder,
        "trial_order": [t.filename for t in trials],
        "n_trials_planned": len(trials),
        "n_responses": len(responses),
        "n_answered": n_answered,
        "background": {"description": plan.describe(), "sources": list(plan.sources),
                       "every_n_trials": plan.every_n, "shuffled": plan.shuffled},
        "timing": timing,
        "environment": environment_info(),
    }
    html, failed = _write_reports(responses, base, info, record)
    log_path = (args.resume if resume_header else base + PARTIAL_SUFFIX)
    if os.path.exists(log_path):
        if "CSV" in failed or (aborted and len(responses) < len(trials)):
            # Keep it: the data isn't safely in a CSV yet, or the session can be
            # finished later with --resume (the reports are then rewritten).
            print(f"Interrupted-session log kept: {log_path}", file=sys.stderr)
        else:
            os.remove(log_path)
    if failed:
        print(f"Reports saved to: {base}.* -- FAILED: {', '.join(failed)} (see messages above)",
              file=sys.stderr)
    else:
        print(f"Reports saved to: {base}.(csv|json|xlsx|html|pdf)")
    if html:
        open_path(html)
    _psychopy_quit(3 if failed else 0)


def _caption_value(choice: str) -> str:
    """Map a caption choice to the Caption enum value ('0'/'1'/'2')."""
    return {"english": "0", "mandarin": "1", "none": "2"}.get(choice, "2")


def _parse_emotions(spec: str | None):
    """Parse a comma-separated emotion list into Emotions, or None for all five.

    Accepts the 3-letter tags (``hap,sad``) and the full names (``happy,sad``),
    in any letter case. Raises ValueError naming anything it doesn't recognise:
    silently dropping an entry would quietly change which emotions are tested.
    """
    if not spec or not spec.strip():
        return None
    from .core import EMOTIONS_IN_ORDER, TAG_TO_EMOTION

    aliases = dict(TAG_TO_EMOTION)
    aliases.update({e.label.lower(): e for e in EMOTIONS_IN_ORDER})
    chosen, unknown = [], []
    for item in (t.strip().lower() for t in spec.split(",")):
        if not item:
            continue
        emotion = aliases.get(item)
        if emotion is None:
            unknown.append(item)
        elif emotion not in chosen:
            chosen.append(emotion)
    if unknown:
        raise ValueError(
            f"Unknown emotion(s): {', '.join(unknown)}. Use hap, sca, neu, sad, ang "
            "(or happy, scared, neutral, sad, angry)."
        )
    return chosen or None


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
    try:
        tone = calibration_tone(rms, seconds, rate=rate)
    except ValueError as exc:                    # would clip, or an absurd length
        print(str(exc), file=sys.stderr)
        return 2
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        wav = fh.name
    try:
        sf.write(wav, tone, rate)
        snd = sound.Sound(wav, stereo=False)
        snd.play()
        core.wait(seconds + 0.2)
        snd.stop()
    finally:
        try:
            os.remove(wav)                        # ~5 MB per minute of tone used to leak
        except OSError:
            pass
    _psychopy_quit(0)


def build_parser() -> argparse.ArgumentParser:
    """The ``emognition`` command line (also used by tests to check ``to_argv()``)."""
    from .core.backgrounds import DEFAULT_EVERY_N, MAX_EVERY_N, MIN_EVERY_N

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
                        help="folder for output reports (default: save_location/ next to "
                             "the app, or in the current folder when run from source)")
    parser.add_argument("--mode", choices=["test", "passive", "active"],
                        default="test",
                        help="session mode: test (default), passive training, "
                             "or active training with feedback")
    parser.add_argument("--background", default="default", metavar="SPEC",
                        help="participant-window background: 'default' (calm gradient), "
                             "'none' (plain), 'slideshow' (all pictures), a picture file, "
                             "or a folder of pictures (slideshow)")
    parser.add_argument("--background-every", type=int, default=DEFAULT_EVERY_N, metavar="N",
                        help=f"slideshow: change picture every N trials "
                             f"({MIN_EVERY_N}-{MAX_EVERY_N}, default {DEFAULT_EVERY_N})")
    parser.add_argument("--background-shuffle", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="slideshow: shuffle the picture order (default: on)")
    parser.add_argument("--seed", type=int, default=None,
                        help="random seed for the trial (and picture) order; recorded in "
                             "every report so a session can be reproduced (default: random)")
    parser.add_argument("--resume", default=None, metavar="LOG",
                        help="continue an interrupted session from its .partial.jsonl "
                             "autosave log (same settings and trial order)")
    parser.add_argument("--no-begin", action="store_true",
                        help="start straight away, without the Begin screen (automation)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
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
