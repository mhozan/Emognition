# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Phase-0 timing spike: prove that audio-onset-synced reaction times are sane.

This is NOT the app. It is the smallest possible end-to-end loop that exercises the
one technical risk that could sink the whole port: *can we, on this machine, play a
clip and measure a reaction time against its onset/offset with millisecond accuracy?*

Pipeline under test:
  - PsychoPy ``sound`` on the PsychoToolbox (``ptb``) backend  -> low-latency, schedulable audio
  - PsychoPy ``hardware.keyboard.Keyboard``                    -> PTB-timestamped key presses
  - audio onset scheduled to a known clock time, RT measured from there

Reaction time, two ways (the user asked for both; offset is the default, matching the
original ``reactiontime.m`` which measured from the audio *stop* instant -1002 to the
click instant -1001):

    rt_from_onset  = t_press - t_audio_onset
    rt_from_offset = t_press - (t_audio_onset + clip_duration)   # <-- default / legacy

Run it (needs a display + audio device):
    .venv/bin/python scripts/timing_spike.py
Press the key shown on screen as soon as each clip finishes; ESC to quit.
"""

from __future__ import annotations

import os
import sys

# IMPORTANT: the audio backend must be chosen BEFORE psychopy.sound is imported.
# We force PsychoToolbox first (lowest latency, sample-accurate scheduling), then
# fall back to sounddevice if PTB can't initialise on this box.
from psychopy import prefs  # noqa: E402

prefs.hardware["audioLib"] = ["ptb", "sounddevice"]

# Make 'emognition' importable when run straight from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Defuse the PsychoPy TextStim/PsychoToolbox SystemError race BEFORE creating any
# window/keyboard/sound threads. See emognition.runtime.harden_psychopy.
from emognition.runtime import harden_psychopy  # noqa: E402

harden_psychopy()

import psychtoolbox as ptb  # noqa: E402
from psychopy import core, sound, visual  # noqa: E402
from psychopy.hardware import keyboard  # noqa: E402

from emognition.naming import scan_stimuli  # noqa: E402

ASSETS_AUDIO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "audio"
)

# We'll ask the participant to press the number key matching the emotion (1..5).
EMO_TO_KEY = {1: "1", 2: "2", 3: "3", 4: "4", 5: "5"}


def main() -> int:
    stimuli = scan_stimuli(ASSETS_AUDIO)   # canonical (BIDS) and legacy names
    if not stimuli:
        print(f"No stimuli found in {ASSETS_AUDIO}", file=sys.stderr)
        return 1

    # A small windowed (not full-screen) display is plenty for a timing check.
    win = visual.Window(
        size=(900, 600), color=(-0.2, -0.2, -0.2), units="height", fullscr=False
    )
    print(f"Audio backend in use: {sound.Sound.__module__}")

    kb = keyboard.Keyboard()
    msg = visual.TextStim(win, text="", height=0.05, wrapWidth=1.2)

    # Open ONE audio stream and reuse it for every clip (snd.setSound swaps the
    # buffer). Constructing a fresh sound.Sound per clip opens a new exclusive
    # ALSA stream and fails on the 2nd clip; one shared stream is also lower
    # latency. (Homage: the original juggled a single Java/MATLAB player too.)
    snd = sound.Sound(stimuli[0].path, stereo=True)

    results = []
    # Test the first few clips -- enough to eyeball that RTs are plausible.
    for i, stim in enumerate(stimuli[:5], start=1):
        snd.setSound(stim.path)
        duration = snd.getDuration()
        want_key = EMO_TO_KEY[int(stim.emotion)]

        msg.text = (
            f"Clip {i}/{min(5, len(stimuli))}\n\n"
            f"Listen, then press '{want_key}' for {stim.emotion.label}\n"
            f"(the correct answer -- this is just a timing test)\n\n"
            f"ESC to quit"
        )
        msg.draw()
        win.flip()

        # Schedule audio onset a touch in the future so PTB can start it precisely,
        # then take that scheduled time as our zero. (Homage: the original tracked a
        # -1002 'stop' instant; here we derive offset analytically from duration.)
        kb.clearEvents()
        now = ptb.GetSecs()
        onset = now + 0.20
        snd.play(when=onset)

        # Busy-wait the ~200 ms to onset, then zero the keyboard clock AT onset.
        while ptb.GetSecs() < onset:
            pass
        kb.clock.reset()  # t = 0 is now the audio onset

        keys = kb.waitKeys(keyList=list(EMO_TO_KEY.values()) + ["escape"])
        snd.stop()
        if not keys or keys[0].name == "escape":
            break

        press = keys[0]
        rt_from_onset = press.rt
        rt_from_offset = press.rt - duration
        correct = press.name == want_key
        results.append((stim.filename, duration, rt_from_onset, rt_from_offset, correct))

        print(
            f"[{i}] {stim.filename:<16} dur={duration:6.3f}s  "
            f"RT(onset)={rt_from_onset:7.3f}s  RT(offset)={rt_from_offset:7.3f}s  "
            f"pressed='{press.name}' correct={correct}"
        )

    win.close()

    print("\n--- timing spike summary ---")
    if results:
        offs = [r[3] for r in results]
        print(f"trials: {len(results)}")
        print(f"mean RT from offset (default): {sum(offs) / len(offs):.3f} s")
        print("If these RTs look like plausible human reaction times (~0.2-1.5 s "
              "from offset), the audio/timing pipeline works on this machine.")
    else:
        print("No trials completed.")
    core.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
