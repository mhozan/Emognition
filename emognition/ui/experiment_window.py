# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""The experiment window: play clips, collect responses, optionally give feedback.

This is the first piece that touches PsychoPy's drawing/timing machinery. It is
deliberately thin: it *presents* stimuli and *captures* responses, then hands
plain :class:`~emognition.core.Response` objects to the UI-free core for scoring.
No statistics live here.

Three session modes (see :class:`~emognition.core.SessionMode`):

* **TEST** -- standard. Clips play, participant responds, no feedback.
* **PASSIVE_TRAINING** -- clips play, correct answer glows for ``feedback_duration``
  seconds, participant does not respond. Use before a test block to teach the
  emotion-face mapping.
* **ACTIVE_TRAINING** -- participant responds, then the correct answer glows green
  and (if wrong) their choice glows orange for ``feedback_duration`` seconds.
  Responses are recorded so a learning-curve is available in the report.

The trial loop (Test mode)::

    for each clip:
        show the N emoticon buttons (greyed)
        schedule the audio to start at a known instant  -> that instant is t=0
        spin the draw/flip loop, polling keyboard + mouse, until a response
        RT = (response time) - (t=0); offset RT = onset RT - clip duration

Two response modalities, one shared clock (reset at audio onset):
  * number keys 1..N  -> pyglet keyboard via psychopy.event
  * clicking a face   -> mouse, faithful to the original GUI
Both are timed at frame resolution against a clock zeroed at the (precisely
scheduled) audio onset; we store which modality produced each RT.

Why not PsychoToolbox's keyboard (sub-ms)? Its PsychHID C thread intermittently
corrupts the Python heap on this Linux stack -> random segfaults in the garbage
collector. iohub (separate process) is crash-free but its keyboard event
timestamps were unreliable here. The pyglet path is in-process, robust, and its
~refresh-rate resolution is dominated by audio-output latency anyway.
"""

from __future__ import annotations

from dataclasses import dataclass

# Audio backend + TextStim race fix MUST be configured before importing
# psychopy.sound / creating any TextStim. Doing it here guarantees the ordering
# no matter who imports this module.
from ..runtime import configure_prefs, harden_psychopy

configure_prefs()
harden_psychopy()

import numpy as np  # noqa: E402
import psychtoolbox as ptb  # noqa: E402  (low-level clock: ptb.GetSecs)
import soundfile as sf  # noqa: E402
from psychopy import core, event, sound, visual  # noqa: E402

from ..core import EMOTIONS_IN_ORDER, Emotion, Response, SessionMode, Stimulus, reaction_time  # noqa: E402
from ..core.timing import ReactionTime  # noqa: E402
from .assets import Caption, emoticon_path, replay_button_path  # noqa: E402

# Sentinel returned by the response loop when the participant asks to replay.
_REPLAY = "__replay__"
# Frames per second for the amplitude envelope driving the LED.
_ENVELOPE_FPS = 60

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
        number: int,
        pos: tuple[float, float],
        size: float,
        caption: Caption,
    ) -> None:
        self.emotion = emotion
        self.number = number
        self.stim = visual.ImageStim(
            win,
            image=emoticon_path(emotion, caption),
            pos=pos,
            size=(size, size),  # square; window 'height' units keep aspect honest
        )
        # A small key-hint label to the left of the face (1..N for the buttons
        # actually shown, not the emotion's canonical code).
        self.label = visual.TextStim(
            win,
            text=str(number),
            pos=(pos[0] - size * 0.85, pos[1]),
            height=size * 0.45,
            color="white",
        )
        # Training-feedback glow: a filled circle drawn *behind* the face image.
        # Left colourless/invisible until _show_feedback() activates it.
        # Green = correct answer; orange = participant's wrong choice.
        self._ring = visual.Circle(
            win,
            radius=size * 0.58,
            pos=pos,
            edges=32,
            fillColor=None,
            lineColor=None,
        )

    def draw(self, enabled: bool = True, highlight: str | None = None) -> None:
        """Draw the face; dim it while a clip is playing or during feedback.

        Args:
            enabled:   Full opacity when True (response phase); 0.3 when False
                       (playback phase, buttons not yet active).
            highlight: Training-feedback state for *this* button:
                       ``"correct"`` -- green glow, full opacity;
                       ``"wrong"``   -- orange glow, full opacity (bad choice);
                       ``"dim"``     -- almost invisible (not the focus);
                       ``None``      -- normal enabled/disabled rendering.
        """
        opacity = 1.0 if enabled else 0.3

        if highlight == "correct":
            self._ring.fillColor = (-1.0, 1.0, -1.0)   # bright green
            self._ring.opacity = 0.55
            self._ring.draw()
            opacity = 1.0
        elif highlight == "wrong":
            self._ring.fillColor = (1.0, 0.2, -1.0)    # orange-red
            self._ring.opacity = 0.55
            self._ring.draw()
            opacity = 1.0
        elif highlight == "dim":
            opacity = 0.12   # nearly invisible; draws attention to the highlighted button

        self.stim.opacity = opacity
        self.label.opacity = opacity
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
        emotions: list[Emotion] | None = None,
        button_size: float = 0.16,
        allow_replays: bool = False,
        amp_visualizer: bool = False,
        volume: float = 0.8,
        mode: SessionMode = SessionMode.TEST,
        feedback_duration: float = 1.5,
    ) -> None:
        self.win = win
        self.mouse = event.Mouse(win=win, visible=True)
        self.allow_replays = allow_replays
        self.amp_visualizer = amp_visualizer
        self.volume = max(0.0, min(1.0, volume))
        self.mode = mode
        self.feedback_duration = max(0.3, feedback_duration)
        # One clock, reset at each clip's audio onset; every RT is measured
        # against it (keyboard via psychopy.event, mouse via this clock).
        self.clock = core.Clock()
        self._envelope: np.ndarray = np.zeros(0)   # current clip's 0..1 RMS envelope
        self._sound: sound.Sound | None = None     # one reusable audio stream
        self._progress_frac = 0.0
        self._close_requested = False              # set when the window's X is clicked

        # Mode-specific "listen" prompt (shown during playback, before response).
        self._listen_prompt = {
            SessionMode.TEST:             "Listen...",
            SessionMode.PASSIVE_TRAINING: "Listen carefully.",
            SessionMode.ACTIVE_TRAINING:  "Listen, then choose.",
        }[mode]

        # Show only the emotions being tested, in canonical order, laid out as a
        # vertically-centred column on the right and renumbered 1..N. (Happy-vs-Sad
        # -> two centred buttons keyed 1 and 2.) The number keys map to THESE.
        active = [e for e in EMOTIONS_IN_ORDER if emotions is None or e in set(emotions)]
        n = len(active)
        spacing = 0.18
        ys = [((n - 1) / 2 - i) * spacing for i in range(n)]
        self.buttons = [
            EmotionButton(win, emo, number=i + 1, pos=(0.45, y),
                          size=button_size, caption=caption)
            for i, (emo, y) in enumerate(zip(active, ys))
        ]
        self.key_map: dict[str, Emotion] = {str(i + 1): emo for i, emo in enumerate(active)}

        # Progress BAR (no text): a grey track with a green fill proportional to
        # how far through the block we are.
        self._progress_track = visual.Rect(
            win, width=0.6, height=0.022, pos=(0.0, 0.44),
            fillColor=(-0.4, -0.4, -0.4), lineColor=None,
        )
        self._progress_fill = visual.Rect(
            win, width=0.0, height=0.022, pos=(-0.3, 0.44),
            fillColor=(-0.2, 0.5, -0.2), lineColor=None, anchor="left",
        )
        self.prompt = visual.TextStim(
            win, text="Listen, then choose the emotion you heard.",
            pos=(-0.15, 0.05), height=0.05, color="white", wrapWidth=0.7,
        )

        # Amplitude "LED": top-left, brightens with the audio level; shown only
        # DURING playback when amp_visualizer is on (revives volumeLED.m).
        self.led = visual.Circle(
            win, radius=0.03, pos=(-0.45, 0.4), edges=32,
            fillColor=(-1, -1, -1), lineColor=(-0.4, -0.4, -0.4),
        )
        # Replay button: bottom-left, shown only after offset when replays are
        # allowed ('r' also replays). Re-zeros the RT clock to the new onset.
        self.replay_button = visual.ImageStim(
            win, image=replay_button_path(), pos=(-0.42, -0.38), size=(0.12, 0.12),
        )

        # Make the window's X (close) button quit the session, like Escape. In
        # fullscreen there is no titlebar/X, so this only matters when windowed.
        try:
            self.win.winHandle.on_close = self._request_close
        except Exception:
            pass

    def _request_close(self) -> None:
        """Window X clicked: flag for the loops to abort (don't destroy the GL win)."""
        self._close_requested = True

    # -- public API -------------------------------------------------------

    def run(self, trials: list[Stimulus]) -> list[Response]:
        """Present every trial in order; return one Response per responding trial.

        Passive training returns no responses (the list will be empty). Active
        training and Test return one Response per trial.

        Raises:
            ExperimentAborted: if Escape is pressed; the responses collected so
                far are attached on the exception's ``.partial`` attribute.
        """
        self._sound = sound.Sound(trials[0].path, stereo=True)

        responses: list[Response] = []
        try:
            for i, stim in enumerate(trials, start=1):
                result = self._present_trial(stim, i, len(trials))
                if result is not None:       # passive training produces no response
                    responses.append(result)
        except ExperimentAborted as abort:
            abort.partial = responses  # type: ignore[attr-defined]
            raise
        return responses

    # -- internals --------------------------------------------------------

    def _present_trial(
        self, stim: Stimulus, index: int, total: int
    ) -> "Response | None":
        """Dispatch to the mode-appropriate trial implementation."""
        if self.mode == SessionMode.PASSIVE_TRAINING:
            return self._present_passive_trial(stim, index, total)
        return self._present_responding_trial(stim, index, total)

    def _present_passive_trial(
        self, stim: Stimulus, index: int, total: int
    ) -> None:
        """Passive training: play the clip, reveal the correct label, advance.

        No response is collected. The correct button glows green for
        ``self.feedback_duration`` seconds so the participant learns the mapping.
        Returns ``None`` (caller skips it when building the response list).
        """
        assert self._sound is not None
        self._load_clip(stim.path)
        duration = self._sound.getDuration()
        self._progress_frac = index / total

        self._draw_scene(enabled=False)
        self.win.flip()
        self._play_and_wait_offset(duration)
        self._show_feedback(stim.emotion, chosen=None)
        self._sound.stop()
        return None

    def _present_responding_trial(
        self, stim: Stimulus, index: int, total: int
    ) -> Response:
        """Test / Active-training: play, collect response, optionally show feedback.

        Active training adds a visual feedback phase after the response:
        correct button = green, wrong choice = orange (if the participant erred).
        """
        assert self._sound is not None
        self._load_clip(stim.path)
        duration = self._sound.getDuration()
        self._progress_frac = index / total

        self._draw_scene(enabled=False)
        self.win.flip()

        n_replays = 0
        self._play_and_wait_offset(duration)
        while True:
            outcome = self._await_response()
            if outcome is _REPLAY:
                n_replays += 1
                self._play_and_wait_offset(duration)   # re-zeros the clock
                continue
            press = outcome
            break

        rt: ReactionTime = reaction_time(
            press_time=press.rt_onset,    # measured from the latest playback's onset
            onset_time=0.0,
            clip_duration=duration,
        )

        # Active training: flash feedback before moving on.
        if self.mode == SessionMode.ACTIVE_TRAINING:
            self._show_feedback(stim.emotion, chosen=press.emotion)

        self._sound.stop()
        return Response(
            stimulus=stim,
            responded=press.emotion,
            rt_onset=rt.from_onset,
            rt_offset=rt.from_offset,
            n_replays=n_replays,
        )

    def _show_feedback(self, correct: Emotion, chosen: "Emotion | None") -> None:
        """Highlight the correct button (and the wrong choice if any) for a beat.

        Drives the training feedback display:
        * Passive training  -- ``chosen`` is None; only the correct button glows.
        * Active training   -- correct glows green; if ``chosen != correct`` the
          participant's choice also glows orange so they see what they got wrong.
        All other buttons dim to near-invisible so the focus is clear.
        """
        correct_name = correct.name.capitalize()
        if chosen is None:
            prompt = f"This was: {correct_name}"
        elif chosen == correct:
            prompt = "Correct!"
        else:
            prompt = f"Correct answer: {correct_name}"

        countdown = core.CountdownTimer(self.feedback_duration)
        while countdown.getTime() > 0:
            if "escape" in event.getKeys() or self._close_requested:
                raise ExperimentAborted()
            self._draw_scene(
                enabled=False,
                feedback_correct=correct,
                feedback_chosen=chosen,
                prompt_override=prompt,
            )
            self.win.flip()
        event.clearEvents()

    def _load_clip(self, path: str) -> None:
        """Point the reusable stream at *path* and (re)compute its LED envelope."""
        assert self._sound is not None
        self._sound.setSound(path)
        self._envelope = self._compute_envelope(path) if self.amp_visualizer else np.zeros(0)

    @staticmethod
    def _compute_envelope(path: str, fps: int = _ENVELOPE_FPS) -> np.ndarray:
        """Return a normalised (0..1) short-time RMS envelope at *fps* samples/sec."""
        data, rate = sf.read(path)
        mono = data if data.ndim == 1 else data.mean(axis=1)
        hop = max(1, rate // fps)
        frames = [
            float(np.sqrt(np.mean(mono[i:i + hop] ** 2)))
            for i in range(0, len(mono), hop)
        ]
        env = np.asarray(frames, dtype=float)
        peak = env.max() if env.size else 0.0
        return env / peak if peak > 0 else env

    def _amplitude_at(self, t: float) -> float:
        """LED level for playback time *t* (0 if past the envelope / no envelope)."""
        if self._envelope.size == 0:
            return 0.0
        idx = int(t * _ENVELOPE_FPS)
        return float(self._envelope[idx]) if 0 <= idx < self._envelope.size else 0.0

    def _play_and_wait_offset(self, duration: float) -> None:
        """Schedule the clip, zero the clock at onset, and hold (greyed, LED live)
        until the clip finishes. Escape quits; early key presses are discarded."""
        assert self._sound is not None
        try:
            self._sound.volume = self.volume     # experimenter-set playback level
        except Exception:
            pass
        event.clearEvents("keyboard")
        now = ptb.GetSecs()
        onset = now + _ONSET_LEAD_SECONDS
        self._sound.play(when=onset)             # sample-accurate scheduled start
        while ptb.GetSecs() < onset:             # brief spin to the exact instant
            pass
        self.clock.reset()                        # t = 0 is the audio onset
        self.mouse.clickReset()

        while self.clock.getTime() < duration:
            if "escape" in event.getKeys() or self._close_requested:  # drains presses
                raise ExperimentAborted()
            self._draw_scene(enabled=False, amplitude=self._amplitude_at(self.clock.getTime()))
            self.win.flip()
        event.clearEvents()

    def _await_response(self) -> "_Press | str":
        """Poll input until a response (or a replay request) arrives."""
        keys = list(self.key_map) + ["escape"]
        if self.allow_replays:
            keys.append("r")
        mouse_was_down = self.mouse.getPressed()[0] == 1  # ignore a held-over click
        while True:
            if self._close_requested:
                raise ExperimentAborted()
            for name, t in event.getKeys(keyList=keys, timeStamped=self.clock):
                if name == "escape":
                    raise ExperimentAborted()
                if name == "r":
                    return _REPLAY
                return _Press(self.key_map[name], t, "key")

            mouse_down = self.mouse.getPressed()[0] == 1
            if mouse_down and not mouse_was_down:
                if self.allow_replays and self.replay_button.contains(self.mouse.getPos()):
                    return _REPLAY
                for button in self.buttons:
                    if button.clicked_by(self.mouse):
                        return _Press(button.emotion, self.clock.getTime(), "mouse")
            mouse_was_down = mouse_down

            self._draw_scene(enabled=True)
            self.win.flip()

    def _draw_scene(
        self,
        *,
        enabled: bool = True,
        amplitude: float = 0.0,
        feedback_correct: "Emotion | None" = None,
        feedback_chosen: "Emotion | None" = None,
        prompt_override: str | None = None,
    ) -> None:
        """Draw one frame: prompt, buttons, progress, LED, and replay button.

        Args:
            enabled:          Dim buttons (False) while a clip plays; full (True)
                              when awaiting response.
            amplitude:        0..1 LED level, driven by the RMS envelope.
            feedback_correct: When set (training modes), the button for this
                              emotion gets a green glow.
            feedback_chosen:  When set and different from *feedback_correct*, this
                              button gets an orange glow (wrong choice).
            prompt_override:  Replace the default prompt text for this frame
                              (used during the feedback phase).
        """
        # Determine prompt text for this frame.
        if prompt_override is not None:
            self.prompt.text = prompt_override
        elif enabled:
            self.prompt.text = "Listen, then choose the emotion you heard."
        else:
            self.prompt.text = self._listen_prompt

        self.prompt.draw()

        # Buttons: apply feedback highlights when in a training feedback phase.
        for button in self.buttons:
            if feedback_correct is not None:
                if button.emotion == feedback_correct:
                    hl: "str | None" = "correct"
                elif feedback_chosen is not None and button.emotion == feedback_chosen:
                    hl = "wrong"
                else:
                    hl = "dim"
            else:
                hl = None
            button.draw(enabled, highlight=hl)

        # Progress bar (no text): green fill = fraction of the block completed.
        self._progress_track.draw()
        self._progress_fill.width = max(0.0, min(1.0, self._progress_frac)) * 0.6
        self._progress_fill.draw()

        # Amplitude LED: only while a clip is playing (responses disabled).
        if self.amp_visualizer and not enabled:
            green = -1.0 + 2.0 * max(0.0, min(1.0, amplitude))  # -1 (off)..+1 (full)
            self.led.fillColor = (-1.0, green, -1.0)
            self.led.draw()
        # Replay button: only after the clip has finished (response phase).
        if self.allow_replays and enabled:
            self.replay_button.draw()
