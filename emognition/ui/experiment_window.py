# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The Test-mode experiment window: play a clip, collect a response + RT.

This is the first piece that touches PsychoPy's drawing/timing machinery. It is
deliberately thin: it *presents* stimuli and *captures* responses, then hands
plain :class:`~emognition.core.Response` objects to the UI-free core for scoring.
No statistics live here.

The trial loop, conceptually::

    for each clip:
        show the 5 emoticon buttons
        schedule the audio to start at a known instant  -> that instant is t=0
        spin the draw/flip loop, polling keyboard + mouse, until a response
        RT = (response time) - (t=0); offset RT = onset RT - clip duration

Two response modalities, one shared clock (reset at audio onset):
  * number keys 1-5  -> PsychoToolbox-timestamped, sub-millisecond precision
  * clicking a face  -> frame-resolution (~16 ms), faithful to the original GUI
We store which modality produced each RT so the precision is never misrepresented.
"""

from __future__ import annotations

from dataclasses import dataclass

# Audio backend + TextStim race fix MUST be configured before importing
# psychopy.sound / creating any TextStim. Doing it here guarantees the ordering
# no matter who imports this module.
from ..runtime import configure_prefs, harden_psychopy

configure_prefs()
harden_psychopy()

import psychtoolbox as ptb  # noqa: E402  (low-level clock: ptb.GetSecs)
from psychopy import event, sound, visual  # noqa: E402
from psychopy.hardware import keyboard  # noqa: E402

from ..core import EMOTIONS_IN_ORDER, Emotion, Response, Stimulus, reaction_time  # noqa: E402
from ..core.timing import ReactionTime  # noqa: E402
from .assets import Caption, emoticon_path  # noqa: E402

# Map the number keys to emotions, matching the original button tags
# (1=Happy .. 5=Angry) and our canonical Emotion ordering.
KEY_TO_EMOTION: dict[str, Emotion] = {
    str(int(emo)): emo for emo in EMOTIONS_IN_ORDER
}

# How far in the future to schedule each clip's onset. PsychoToolbox needs a
# small lead time to arm the sound for a sample-accurate start; 200 ms is plenty
# and imperceptible.
_ONSET_LEAD_SECONDS = 0.20


class ExperimentAborted(Exception):
    """Raised when the participant/experimenter quits early (Escape)."""


@dataclass(frozen=True, slots=True)
class _Press:
    """A raw response event: which emotion, when (s since onset), how it arrived."""

    emotion: Emotion
    rt_onset: float
    modality: str  # "key" or "mouse"


class EmotionButton:
    """One clickable emoticon face, plus the emotion it stands for.

    Thin wrapper around a PsychoPy :class:`~psychopy.visual.ImageStim`. Keeping the
    emotion paired with its sprite (rather than juggling parallel lists, as the
    MATLAB code did with ``S.pbe(1..5)``) makes hit-testing self-explanatory.
    """

    def __init__(
        self,
        win: visual.Window,
        emotion: Emotion,
        pos: tuple[float, float],
        size: float,
        caption: Caption,
    ) -> None:
        self.emotion = emotion
        self.stim = visual.ImageStim(
            win,
            image=emoticon_path(emotion, caption),
            pos=pos,
            size=(size, size),  # square; window 'height' units keep aspect honest
        )
        # A small key-hint label to the left of the face ("1".."5").
        self.label = visual.TextStim(
            win,
            text=str(int(emotion)),
            pos=(pos[0] - size * 0.85, pos[1]),
            height=size * 0.45,
            color="white",
        )

    def draw(self) -> None:
        self.stim.draw()
        self.label.draw()

    def clicked_by(self, mouse: event.Mouse) -> bool:
        """True if the cursor is currently inside this face's bounds."""
        return bool(self.stim.contains(mouse.getPos()))


class TestExperiment:
    """Runs Test mode: present each clip, collect a response, return the trials.

    Construct it with an open :class:`~psychopy.visual.Window`, then call
    :meth:`run` with the ordered stimuli. It does not create or close the window
    (the caller owns that), which keeps this class focused and reusable.
    """

    def __init__(
        self,
        win: visual.Window,
        *,
        caption: Caption = Caption.NONE,
        button_size: float = 0.16,
    ) -> None:
        self.win = win
        self.kb = keyboard.Keyboard()       # PTB-timestamped key events
        self.mouse = event.Mouse(win=win, visible=True)

        # One reusable audio stream. We swap the buffer per clip with setSound();
        # constructing a new Sound per clip opens a new (exclusive) device stream
        # and fails on the 2nd clip -- learned the hard way during the spike.
        self._sound: sound.Sound | None = None

        # Lay the five faces out as a vertical column on the right, top→bottom in
        # canonical order (Happy, Scared, Neutral, Sad, Angry) -- same order the
        # original stacked them.
        ys = [0.34, 0.17, 0.0, -0.17, -0.34]
        self.buttons = [
            EmotionButton(win, emo, pos=(0.45, y), size=button_size, caption=caption)
            for emo, y in zip(EMOTIONS_IN_ORDER, ys)
        ]

        self.progress = visual.TextStim(
            win, text="", pos=(0.0, 0.45), height=0.05, color="white"
        )
        self.prompt = visual.TextStim(
            win,
            text="Listen, then choose the emotion you heard.",
            pos=(-0.2, 0.0),
            height=0.045,
            color="white",
            wrapWidth=0.6,
        )

    # -- public API -------------------------------------------------------

    def run(self, trials: list[Stimulus]) -> list[Response]:
        """Present every trial in order; return one Response per trial.

        Raises:
            ExperimentAborted: if Escape is pressed; the responses collected so
                far are attached on the exception's ``.partial`` attribute.
        """
        # Prime the reusable stream with the first clip's format.
        self._sound = sound.Sound(trials[0].path, stereo=True)

        responses: list[Response] = []
        try:
            for i, stim in enumerate(trials, start=1):
                responses.append(self._present_trial(stim, i, len(trials)))
        except ExperimentAborted as abort:
            abort.partial = responses  # type: ignore[attr-defined]
            raise
        return responses

    # -- internals --------------------------------------------------------

    def _present_trial(self, stim: Stimulus, index: int, total: int) -> Response:
        """Present one clip and block until the participant responds."""
        assert self._sound is not None
        self._sound.setSound(stim.path)
        duration = self._sound.getDuration()

        # Draw the response screen once so it's visible as the audio begins.
        self._draw_scene(progress=f"{index} / {total}")
        self.win.flip()

        onset = self._start_audio_and_zero_clock()
        press = self._await_response()

        rt: ReactionTime = reaction_time(
            press_time=press.rt_onset,  # already measured from onset (t=0)
            onset_time=0.0,
            clip_duration=duration,
        )
        self._sound.stop()
        return Response(
            stimulus=stim,
            responded=press.emotion,
            rt_onset=rt.from_onset,
            rt_offset=rt.from_offset,
            n_replays=0,  # replays come in Phase 2
        )

    def _start_audio_and_zero_clock(self) -> float:
        """Schedule the clip and reset the keyboard clock to its onset (t=0)."""
        assert self._sound is not None
        self.kb.clearEvents()
        now = ptb.GetSecs()
        onset = now + _ONSET_LEAD_SECONDS
        self._sound.play(when=onset)            # sample-accurate scheduled start
        while ptb.GetSecs() < onset:            # brief spin to the exact instant
            pass
        self.kb.clock.reset()                    # now t=0 is the audio onset
        self.mouse.clickReset()
        return onset

    def _await_response(self) -> _Press:
        """Spin the draw/flip loop, polling input, until a response arrives."""
        mouse_was_down = self.mouse.getPressed()[0] == 1  # ignore a held-over click
        while True:
            # 1) Keyboard (precise): getKeys returns discrete press events with an
            #    .rt already relative to our onset-zeroed clock.
            for key in self.kb.getKeys(list(KEY_TO_EMOTION) + ["escape"]):
                if key.name == "escape":
                    raise ExperimentAborted()
                return _Press(KEY_TO_EMOTION[key.name], key.rt, "key")

            # 2) Mouse (frame-resolution): accept only a *fresh* press (edge), so a
            #    click held from the previous trial doesn't auto-trigger.
            mouse_down = self.mouse.getPressed()[0] == 1
            if mouse_down and not mouse_was_down:
                for button in self.buttons:
                    if button.clicked_by(self.mouse):
                        return _Press(button.emotion, self.kb.clock.getTime(), "mouse")
            mouse_was_down = mouse_down

            # 3) Keep the window alive and frame-lock the polling.
            self._draw_scene(progress=None)
            self.win.flip()

    def _draw_scene(self, progress: str | None) -> None:
        """Draw one frame: prompt, buttons, and (optionally) the progress text."""
        self.prompt.draw()
        for button in self.buttons:
            button.draw()
        if progress is not None:
            self.progress.text = f"Progress: {progress}"
        self.progress.draw()
