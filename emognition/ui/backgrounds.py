# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Drawing the participant-window background picture (PsychoPy).

Revives the original's background pictures (bgchanger.m) without its cost: MATLAB
ran ``imread`` + ``image()`` + ``drawnow`` inside the response callback, so a
large photo could delay the next trial. Here:

* **One** ``ImageStim`` serves the whole session. PsychoPy allocates a GL pixel
  buffer per ImageStim and never frees it (``clearTextures()`` checks
  ``_pixBuffID`` but the attribute is ``_pixbuffID``), so a stim per picture would
  leak GPU memory at every switch. Re-assigning ``.image`` reuses the buffer.
* Pictures change **only between trials**: :class:`TestExperiment` calls
  :meth:`BackgroundLayer.select` before a trial's first flip -- never while a clip
  plays or a response is being timed. The upcoming picture is decoded in advance
  on a worker thread (Pillow releases the GIL while decoding), so a switch costs a
  single texture upload, made while nothing is being timed.
* Drawing is one textured quad per frame, first in the scene. We don't use
  ``win.backgroundImage``: PsychoPy draws that after each flip, one frame late.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from psychopy import visual

from ..core.backgrounds import CALM_GRADIENT, BackgroundPlan, friendly_name
from ..imaging import DEFAULT_MAX_LUMA, render_background
from .geometry import fit_within

# Upload pictures at most this large; the GPU scales them to the window.
MAX_TEXTURE_SIZE: tuple[int, int] = (1920, 1200)


def _framebuffer_size(win: visual.Window) -> tuple[int, int]:
    """The window's real pixel size (on Retina, the framebuffer, not the points)."""
    size = getattr(win, "frameBufferSize", None)
    if size is None:
        size = win.size
    return int(size[0]), int(size[1])


class BackgroundLayer:
    """The background for one session: holds the plan, the stim and a prefetcher.

    Args:
        win: The participant window.
        plan: Which picture goes with which trial (see core.backgrounds).
        max_luma: Brightness cap for pictures (keeps the white text readable).
        log: Where to report unreadable pictures (stdout -> the session log).
    """

    def __init__(
        self,
        win: visual.Window,
        plan: BackgroundPlan,
        *,
        max_luma: float | None = DEFAULT_MAX_LUMA,
        log: Callable[[str], None] = print,
    ) -> None:
        self.plan = plan
        self._max_luma = max_luma
        self._log = log
        self._size = fit_within(_framebuffer_size(win), MAX_TEXTURE_SIZE)
        self._stim: visual.ImageStim | None = None
        self._current: str | None = None
        self._n_trials = 0
        self._executor: ThreadPoolExecutor | None = None
        self._pending: tuple[str, Future] | None = None
        # The first picture is decoded right away, so the layer can draw before
        # prepare() (scripts/screenshot_experiment.py draws scenes directly).
        if plan.first is not None:
            self._stim = visual.ImageStim(
                win, image=self._render(plan.first), units="norm", size=(2, 2),
                interpolate=True, autoLog=False,
            )
            self._current = plan.first

    # -- queries -----------------------------------------------------------

    @property
    def shows_picture(self) -> bool:
        """True while a photo-like picture is shown (not the gradient or a plain window).

        The experiment puts translucent dark panels behind its text in that case.
        """
        return self._current not in (None, CALM_GRADIENT)

    @property
    def current(self) -> str | None:
        """The background source on screen now (None for a plain window)."""
        return self._current

    @property
    def label(self) -> str:
        """Friendly name of the picture on screen ("" for a plain window), for the data."""
        return friendly_name(self._current) if self._current else ""

    # -- session lifecycle ---------------------------------------------------

    def prepare(self, n_trials: int) -> None:
        """Note the session length and start decoding the second picture, if any."""
        self._n_trials = n_trials
        self._prefetch_after(1)

    def select(self, trial: int) -> None:
        """Show the picture planned for 1-based *trial* (call between trials only)."""
        source = self.plan.source_for_trial(trial)
        if self._stim is None or source is None or source == self._current:
            return
        self._stim.image = self._take(source)   # one texture upload, nothing being timed
        self._current = source
        self._prefetch_after(trial)

    def draw(self) -> None:
        if self._stim is not None:
            self._stim.draw()

    def close(self) -> None:
        """Stop the prefetch worker (doesn't wait for a decode in progress)."""
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self._pending = None

    # -- internals -------------------------------------------------------------

    def _render(self, source: str):
        image, problem = render_background(source, self._size, max_luma=self._max_luma)
        if problem:
            self._log(problem)
        return image

    def _prefetch_after(self, trial: int) -> None:
        """Decode, on the worker thread, the next different picture after *trial*."""
        upcoming = self.plan.next_change_after(trial, self._n_trials)
        if upcoming is None:
            self._pending = None
            return
        source = self.plan.source_for_trial(upcoming)
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="emognition-bg")
        self._pending = (source, self._executor.submit(self._render, source))

    def _take(self, source: str):
        """The decoded image for *source*: the prefetched one if it matches, else decode now."""
        if self._pending is not None and self._pending[0] == source:
            future = self._pending[1]
            self._pending = None
            return future.result()
        return self._render(source)
