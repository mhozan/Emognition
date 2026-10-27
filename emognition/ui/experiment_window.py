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

A session runs in three steps, mirroring the original's "Begin Test" flow
(proceed.m -> pb_beginner.m)::

    prepare(trials)     open the audio stream, decode backgrounds, warm up the GPU
    wait_for_begin()    background + a big "Begin" button; returns the start time
    run(trials)         the trials themselves

The trial loop (Test mode)::

    for each clip:
        (between trials) switch the background picture if the plan says so
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

Frame-loop hygiene: because RTs are sampled once per frame, anything slow inside
the draw loop coarsens them. So nothing in :meth:`TestExperiment._draw_scene`
rebuilds text or allocates colours: label variants, prompts and feedback rings
are all built up front, and the few values that do change (progress, LED) are
only assigned when they actually change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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
from ..core.backgrounds import BackgroundPlan  # noqa: E402
from ..core.timing import ReactionTime  # noqa: E402
from .assets import Caption, emoticon_path, replay_button_path  # noqa: E402
from .backgrounds import BackgroundLayer  # noqa: E402
from .geometry import rounded_rect_vertices  # noqa: E402

# Sentinel returned by the response loop when the participant asks to replay.
_REPLAY = "__replay__"
# Frames per second for the amplitude envelope driving the LED.
_ENVELOPE_FPS = 60
# The LED brightness is quantised so its colour is only re-assigned on a change.
_LED_LEVELS = 32

# How far in the future to schedule each clip's onset. PsychoToolbox needs a
# small lead time to arm the sound for a sample-accurate start; 200 ms is plenty
# and imperceptible.
_ONSET_LEAD_SECONDS = 0.20

# Opacity levels an emoticon button is drawn at (see EmotionButton.draw).
_OPACITY_ENABLED = 1.0    # response phase
_OPACITY_DISABLED = 0.3   # clip playing: not clickable yet
_OPACITY_DIM = 0.12       # training feedback: not the button being taught
_OPACITY_LEVELS = (_OPACITY_ENABLED, _OPACITY_DISABLED, _OPACITY_DIM)

# Progress bar geometry ('height' units). 0.5 wide so it ends just left of the
# key-number column (and of its panel, when a picture is the background).
_PROGRESS_WIDTH = 0.5
_PROGRESS_Y = 0.44

# The prompt line.
_PROMPT_POS = (-0.15, 0.05)
_PROMPT_HEIGHT = 0.05
_PROMPT_WRAP = 0.7
_RESPONSE_PROMPT = "Listen, then choose the emotion you heard."

# Translucent panels behind the text when a picture is the background, so the
# white prompt and key numbers stay readable over any photo.
_PANEL_OPACITY = 0.45
_PANEL_RADIUS = 0.03
_PANEL_PAD = (0.035, 0.022)   # horizontal, vertical padding around a prompt

# The Begin screen: a big friendly target for children; Space/Enter for adults.
_BEGIN_LABEL = "Begin"
_BEGIN_KEYS = ("space", "return", "num_enter")
_BEGIN_SIZE = (0.42, 0.14)
_BEGIN_FILL = (242, 239, 255)          # rgb255: soft lavender-white
_BEGIN_FILL_HOVER = (255, 255, 255)
_BEGIN_TEXT = (42, 34, 80)             # the setup window's title colour
# A short, calm pause after Begin before the first clip (hand away from the mouse).
_BEGIN_SETTLE_SECONDS = 0.5


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
            autoLog=False,
        )
        self._stim_opacity = 1.0
        # A small key-hint label to the left of the face (1..N for the buttons
        # actually shown, not the emotion's canonical code) -- one per opacity
        # level. Assigning TextStim.opacity makes PsychoPy rebuild the whole
        # pyglet Label on the next draw (psychopy/visual/text.py), which used to
        # happen for every button on every frame; switching variants is free.
        self._labels = {
            level: visual.TextStim(
                win, text=str(number), pos=(pos[0] - size * 0.85, pos[1]),
                height=size * 0.45, color="white", opacity=level, autoLog=False,
            )
            for level in _OPACITY_LEVELS
        }
        # Training-feedback glows: filled circles drawn *behind* the face image,
        # pre-coloured (re-assigning fillColor allocates a Color every frame).
        # Green = correct answer; orange = participant's wrong choice.
        ring = dict(radius=size * 0.58, pos=pos, edges=32, lineColor=None, opacity=0.55, autoLog=False)
        self._rings = {
            "correct": visual.Circle(win, fillColor=(-1.0, 1.0, -1.0), **ring),
            "wrong": visual.Circle(win, fillColor=(1.0, 0.2, -1.0), **ring),
        }

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
        ring = self._rings.get(highlight or "")
        if ring is not None:
            ring.draw()
            opacity = _OPACITY_ENABLED
        elif highlight == "dim":
            opacity = _OPACITY_DIM   # nearly invisible; draws attention to the highlighted button
        else:
            opacity = _OPACITY_ENABLED if enabled else _OPACITY_DISABLED

        if opacity != self._stim_opacity:   # cheap for an ImageStim, but skip the churn
            self.stim.opacity = opacity
            self._stim_opacity = opacity
        self.stim.draw()
        self._labels[opacity].draw()

    def warm_up(self) -> None:
        """Draw every variant once (texture upload / display lists) before trial 1."""
        for ring in self._rings.values():
            ring.draw()
        self.stim.draw()
        for label in self._labels.values():
            label.draw()

    def clicked_by(self, mouse: event.Mouse) -> bool:
        """True if the cursor is currently inside this face's bounds."""
        return bool(self.stim.contains(mouse.getPos()))


class BeginButton:
    """The large rounded "Begin" button of the start screen.

    The original's "Begin Test" was a small dark button in the bottom-left corner
    (proceed.m); this one is centred and big enough for a child to find and hit.
    The rounded outline is computed once; ``contains`` tests that exact shape.
    """

    def __init__(self, win: visual.Window, label: str = _BEGIN_LABEL) -> None:
        width, height = _BEGIN_SIZE
        vertices = rounded_rect_vertices(width, height, height / 2.6)
        self._shadow = visual.ShapeStim(
            win, vertices=vertices, pos=(0.006, -0.010), fillColor=(-1, -1, -1),
            lineColor=None, opacity=0.35, autoLog=False,
        )
        self._shape = visual.ShapeStim(
            win, vertices=vertices, pos=(0.0, 0.0), fillColor=_BEGIN_FILL,
            colorSpace="rgb255", lineColor=None, autoLog=False,
        )
        self._text = visual.TextStim(
            win, text=label, pos=(0.0, 0.0), height=height * 0.46, color=_BEGIN_TEXT,
            colorSpace="rgb255", bold=True, autoLog=False,
        )
        self._hover = False

    def contains(self, mouse: event.Mouse) -> bool:
        return bool(self._shape.contains(mouse.getPos()))

    def set_hover(self, hover: bool) -> None:
        """Brighten under the cursor (colour re-assigned only when the state changes)."""
        if hover != self._hover:
            self._shape.fillColor = _BEGIN_FILL_HOVER if hover else _BEGIN_FILL
            self._hover = hover

    def draw(self) -> None:
        self._shadow.draw()
        self._shape.draw()
        self._text.draw()


def _panel(win: visual.Window, left: float, right: float, bottom: float, top: float) -> visual.ShapeStim:
    """A translucent dark rounded panel spanning the given box (window units)."""
    return visual.ShapeStim(
        win,
        vertices=rounded_rect_vertices(right - left, top - bottom, _PANEL_RADIUS),
        pos=((left + right) / 2.0, (bottom + top) / 2.0),
        fillColor=(-1, -1, -1), lineColor=None, opacity=_PANEL_OPACITY, autoLog=False,
    )


def _pixels_per_unit(win: visual.Window) -> tuple[float, float]:
    """Pixels per window unit along x and y (the app uses 'height' units)."""
    width, height = (float(v) for v in win.size)
    units = getattr(win, "units", "height")
    if units == "norm":
        return width / 2.0, height / 2.0
    if units == "pix":
        return 1.0, 1.0
    return height, height


class TestExperiment:
    """Runs a session: present each clip, collect a response, return the trials.

    Construct it with an open :class:`~psychopy.visual.Window`, then call
    :meth:`prepare`, :meth:`wait_for_begin` and :meth:`run` with the ordered
    stimuli (``run`` prepares on its own if needed). It does not create or close
    the window (the caller owns that), which keeps this class focused and
    reusable; call :meth:`close` when done to stop its helper thread.
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
        background: BackgroundPlan | None = None,
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
        self._envelopes: dict[str, np.ndarray] = {}  # per clip, computed in prepare()
        self._sound: sound.Sound | None = None     # one reusable audio stream
        self._prepared = False
        self._progress_frac = 0.0
        self._progress_width: float | None = None   # last width assigned to the fill
        self._led_level: int | None = None          # last quantised LED level
        self._close_requested = False              # set when the window's X is clicked
        # Frame timing is recorded only while the screen animates continuously
        # (playback, waiting for the answer, feedback) -- the deliberate pauses
        # (the 200 ms onset spin, loading between trials) are not dropped frames.
        self.record_timing = True

        # Background: None keeps the plain window colour (what scripts expect).
        self.background = BackgroundLayer(win, background or BackgroundPlan(sources=()))

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

        # Every prompt the session can show, built once (changing TextStim.text
        # rebuilds its pyglet Label; switching between pre-built stims is free),
        # each with a backing panel sized to its text for picture backgrounds.
        self._prompts: dict[str, visual.TextStim] = {}
        self._prompt_panels: dict[str, visual.ShapeStim] = {}
        for text in (self._listen_prompt, _RESPONSE_PROMPT, "Correct!",
                     *(f"This was: {e.label}" for e in active),
                     *(f"Correct answer: {e.label}" for e in active)):
            self._prompt_panel(text)

        # Panel behind the number + face column, used only over a picture.
        label_left = 0.45 - button_size * 0.85 - button_size * 0.35
        half = button_size / 2.0 + 0.025
        self._panels = (
            [_panel(win, label_left, 0.45 + half, ys[-1] - half, ys[0] + half)] if ys else []
        )

        # Progress BAR (no text): a grey track with a green fill proportional to
        # how far through the block we are.
        self._progress_track = visual.Rect(
            win, width=_PROGRESS_WIDTH, height=0.022, pos=(0.0, _PROGRESS_Y),
            fillColor=(-0.4, -0.4, -0.4), lineColor=None, autoLog=False,
        )
        self._progress_fill = visual.Rect(
            win, width=0.0, height=0.022, pos=(-_PROGRESS_WIDTH / 2, _PROGRESS_Y),
            fillColor=(-0.2, 0.5, -0.2), lineColor=None, anchor="left", autoLog=False,
        )

        # Amplitude "LED": top-left, brightens with the audio level; shown only
        # DURING playback when amp_visualizer is on (revives volumeLED.m).
        self.led = visual.Circle(
            win, radius=0.03, pos=(-0.45, 0.4), edges=32,
            fillColor=(-1, -1, -1), lineColor=(-0.4, -0.4, -0.4), autoLog=False,
        )
        # Replay button: bottom-left, shown only after offset when replays are
        # allowed ('r' also replays). Re-zeros the RT clock to the new onset.
        self.replay_button = visual.ImageStim(
            win, image=replay_button_path(), pos=(-0.42, -0.38), size=(0.12, 0.12),
            autoLog=False,
        )
        self._begin_button = BeginButton(win)

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

    def prepare(self, trials: list[Stimulus]) -> None:
        """Get everything ready before the participant is asked to Begin.

        Opens the single reusable audio stream (a second ``sound.Sound`` would
        open a second exclusive ALSA stream and fail), computes the LED envelopes,
        starts decoding the next background picture, and warms up the GPU. Safe to
        call more than once; :meth:`run` calls it if you didn't.
        """
        if self._prepared:
            return
        if not trials:
            raise ValueError("cannot prepare a session with no trials")
        if self._sound is None:
            self._sound = sound.Sound(trials[0].path, stereo=True)
        if self.amp_visualizer:
            for path in dict.fromkeys(t.path for t in trials):
                self._envelopes[path] = self._compute_envelope(path)
        self.background.prepare(len(trials))
        self._warm_up()
        self._prepared = True

    def wait_for_begin(self) -> datetime:
        """Show the Begin screen until the participant (or experimenter) starts.

        A click on the button (press and release inside it) or Space/Enter begins;
        Escape or closing the window raises :class:`ExperimentAborted`. Returns the
        moment Begin was pressed -- the session start, as in the original, where
        pb_beginner.m stamped ``S.pb_begin.UserData = clock`` for the report's
        start/finish/duration.
        """
        try:
            self.win.winHandle.activate()   # keyboard focus, so Space works straight away
        except Exception:
            pass
        event.clearEvents()
        self.mouse.clickReset()
        keys = [*_BEGIN_KEYS, "escape"]
        mouse_was_down = self.mouse.getPressed()[0] == 1
        pressed_inside = False
        while True:
            if self._close_requested:
                raise ExperimentAborted()
            pressed = event.getKeys(keyList=keys)
            if "escape" in pressed:
                raise ExperimentAborted()
            if pressed:
                break
            inside = self._begin_button.contains(self.mouse)
            self._begin_button.set_hover(inside)
            mouse_down = self.mouse.getPressed()[0] == 1
            if mouse_down and not mouse_was_down:
                pressed_inside = inside
            elif mouse_was_down and not mouse_down:
                if pressed_inside and inside:
                    break                       # a complete click on the button
                pressed_inside = False
            mouse_was_down = mouse_down
            self.background.draw()
            self._begin_button.draw()
            self.win.flip()

        begun_at = datetime.now()
        event.clearEvents()                     # the Begin press must not count as a response
        self.mouse.clickReset()
        self._settle(_BEGIN_SETTLE_SECONDS)
        return begun_at

    def run(
        self,
        trials: list[Stimulus],
        *,
        on_trial: "callable | None" = None,
    ) -> list[Response]:
        """Present every trial in order; return one Response per responding trial.

        Passive training returns no responses (the list will be empty). Active
        training and Test return one Response per trial.

        Args:
            on_trial: Optional callback invoked after each trial with
                ``(response_or_none, index, total)``. Used by the experimenter
                monitor window to display live progress without coupling the
                experiment window to Qt.

        Raises:
            ExperimentAborted: if Escape is pressed; the responses collected so
                far are attached on the exception's ``.partial`` attribute.
        """
        self.prepare(trials)
        self.win.frameIntervals = []
        self.win.nDroppedFrames = 0

        responses: list[Response] = []
        try:
            for i, stim in enumerate(trials, start=1):
                # Trial boundary: the only moment the background may change (one
                # texture upload; the clip isn't scheduled yet, nothing is timed).
                self.background.select(i)
                result = self._present_trial(stim, i, len(trials))
                if result is not None:       # passive training produces no response
                    responses.append(result)
                if on_trial is not None:
                    try:
                        on_trial(result, i, len(trials))
                    except Exception:
                        pass   # monitor errors must never crash the experiment
        except ExperimentAborted as abort:
            abort.partial = responses  # type: ignore[attr-defined]
            raise
        finally:
            self._record_frames(False)
        return responses

    def timing_summary(self) -> dict:
        """Display/audio timing QA for the reports (refresh rate, dropped frames, latency).

        Reaction times are sampled once per frame, so the refresh rate and the
        share of dropped frames say how precise this session's RTs really were.
        """
        intervals = np.asarray(self.win.frameIntervals, dtype=float)
        measured = getattr(self.win, "_monitorFrameRate", None)
        period = float(getattr(self.win, "monitorFramePeriod", 0.0) or 0.0)
        summary = {
            "refresh_hz": round(float(measured), 2) if measured else (round(1.0 / period, 2) if period else None),
            "refresh_measured": bool(measured),
            "frames_recorded": int(intervals.size),
            "frames_dropped": int(getattr(self.win, "nDroppedFrames", 0)),
            "frame_interval_ms_mean": round(float(intervals.mean()) * 1000, 3) if intervals.size else None,
            "frame_interval_ms_sd": round(float(intervals.std(ddof=1)) * 1000, 3) if intervals.size > 1 else None,
            "frame_interval_ms_max": round(float(intervals.max()) * 1000, 3) if intervals.size else None,
            "audio_predicted_latency_ms": None,
        }
        try:   # PsychPortAudio's own estimate of output latency
            latency = self._sound.stream.status.get("PredictedLatency") if self._sound else None
            if latency is not None:
                summary["audio_predicted_latency_ms"] = round(float(latency) * 1000, 2)
        except Exception:  # noqa: BLE001 -- QA info only, never fatal
            pass
        return summary

    def close(self) -> None:
        """Release helper resources (the background prefetch thread)."""
        self.background.close()

    # -- internals --------------------------------------------------------

    def _prompt_stim(self, text: str) -> visual.TextStim:
        """The pre-built TextStim showing *text* (built on first use otherwise)."""
        stim = self._prompts.get(text)
        if stim is None:
            stim = visual.TextStim(
                self.win, text=text, pos=_PROMPT_POS, height=_PROMPT_HEIGHT,
                color="white", wrapWidth=_PROMPT_WRAP, autoLog=False,
            )
            self._prompts[text] = stim
        return stim

    def _prompt_panel(self, text: str) -> visual.ShapeStim:
        """The backing panel for *text*, fitted to its rendered size (built once)."""
        panel = self._prompt_panels.get(text)
        if panel is None:
            w_px, h_px = self._prompt_stim(text).boundingBox     # pixels, per PsychoPy
            px_x, px_y = _pixels_per_unit(self.win)
            half_w = w_px / px_x / 2.0 + _PANEL_PAD[0]
            half_h = h_px / px_y / 2.0 + _PANEL_PAD[1]
            x, y = _PROMPT_POS
            panel = _panel(self.win, x - half_w, x + half_w, y - half_h, y + half_h)
            self._prompt_panels[text] = panel
        return panel

    def _warm_up(self) -> None:
        """Draw every stimulus variant once, without showing anything.

        A stim's first draw uploads its texture and compiles its display list;
        doing it here -- then waiting for the GPU and clearing the back buffer
        instead of flipping -- keeps those one-off costs out of trial 1.
        """
        from pyglet import gl

        self.background.draw()
        for panel in (*self._panels, *self._prompt_panels.values()):
            panel.draw()
        self._progress_track.draw()
        self._progress_fill.draw()
        for prompt in self._prompts.values():
            prompt.draw()
        for button in self.buttons:
            button.warm_up()
        self.led.draw()
        self.replay_button.draw()
        self._begin_button.draw()
        gl.glFinish()
        self.win.clearBuffer()

    def _settle(self, seconds: float) -> None:
        """Hold the (greyed) trial screen briefly; Escape still quits."""
        countdown = core.CountdownTimer(seconds)
        while countdown.getTime() > 0:
            if "escape" in event.getKeys(keyList=["escape"]) or self._close_requested:
                raise ExperimentAborted()
            self._draw_scene(enabled=False)
            self.win.flip()
        event.clearEvents()

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
        self._record_frames(False)               # loading the next trial isn't a dropped frame
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
        self._record_frames(False)               # loading the next trial isn't a dropped frame
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
        if chosen is None:
            prompt = f"This was: {correct.label}"
        elif chosen == correct:
            prompt = "Correct!"
        else:
            prompt = f"Correct answer: {correct.label}"

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
        """Point the reusable stream at *path* and pick up its LED envelope."""
        assert self._sound is not None
        self._sound.setSound(path)
        if self.amp_visualizer:
            envelope = self._envelopes.get(path)
            if envelope is None:                       # not seen in prepare()
                envelope = self._envelopes[path] = self._compute_envelope(path)
            self._envelope = envelope
        else:
            self._envelope = np.zeros(0)

    @staticmethod
    def _compute_envelope(path: str, fps: int = _ENVELOPE_FPS) -> np.ndarray:
        """Return a normalised (0..1) short-time RMS envelope at *fps* samples/sec."""
        data, rate = sf.read(path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        hop = max(1, rate // fps)
        n_full = len(mono) // hop
        frames = mono[: n_full * hop].reshape(n_full, hop)
        env = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
        tail = mono[n_full * hop:]                     # the last, partial frame
        if tail.size:
            env = np.append(env, np.sqrt(np.mean(tail.astype(np.float64) ** 2)))
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
        self._record_frames(False)                # the spin below is a deliberate pause
        now = ptb.GetSecs()
        onset = now + _ONSET_LEAD_SECONDS
        self._sound.play(when=onset)             # sample-accurate scheduled start
        while ptb.GetSecs() < onset:             # brief spin to the exact instant
            pass
        self.clock.reset()                        # t = 0 is the audio onset
        self.mouse.clickReset()
        self._record_frames(True)                 # continuous flips from here to the answer

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

    def _record_frames(self, on: bool) -> None:
        """Start/stop PsychoPy's frame-interval recording (restarting resets the clock)."""
        self.win.recordFrameIntervals = bool(on and self.record_timing)

    def _set_progress(self, fraction: float) -> None:
        """Size the progress fill (assigned only when it changes: Rect.width allocates)."""
        width = max(0.0, min(1.0, fraction)) * _PROGRESS_WIDTH
        if width != self._progress_width:
            self._progress_fill.width = width
            self._progress_width = width

    def _set_led(self, amplitude: float) -> None:
        """Set the LED brightness, quantised so the colour changes only on a step."""
        level = round(max(0.0, min(1.0, amplitude)) * _LED_LEVELS)
        if level != self._led_level:
            green = -1.0 + 2.0 * level / _LED_LEVELS   # -1 (off) .. +1 (full)
            self.led.fillColor = (-1.0, green, -1.0)
            self._led_level = level

    def _draw_scene(
        self,
        *,
        enabled: bool = True,
        amplitude: float = 0.0,
        feedback_correct: "Emotion | None" = None,
        feedback_chosen: "Emotion | None" = None,
        prompt_override: str | None = None,
    ) -> None:
        """Draw one frame: background, prompt, buttons, progress, LED, replay button.

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
        # Prompt: pick the pre-built stim for this frame's text.
        if prompt_override is not None:
            text = prompt_override
        elif enabled:
            text = _RESPONSE_PROMPT
        else:
            text = self._listen_prompt

        self.background.draw()
        if self.background.shows_picture:
            for panel in self._panels:
                panel.draw()
            self._prompt_panel(text).draw()
        self._prompt_stim(text).draw()

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
        self._set_progress(self._progress_frac)
        self._progress_fill.draw()

        # Amplitude LED: only while a clip is playing (responses disabled).
        if self.amp_visualizer and not enabled:
            self._set_led(amplitude)
            self.led.draw()
        # Replay button: only after the clip has finished (response phase).
        if self.allow_replays and enabled:
            self.replay_button.draw()
