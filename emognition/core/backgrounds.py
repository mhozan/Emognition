# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Which background picture the participant sees on which trial (UI-free).

The original program could fill the participant window with pictures from a
folder and swap them every few responses -- a way to keep children engaged.

    Homage to the original (bgchanger.m):
        indx=1+ceil(S.keypresscount/S.intervl);
        while  indx > length(S.bgimagestruct)
            indx=indx-length(S.bgimagestruct); %restart showing backgrounds from the beginning
        end

MATLAB counted *responses* and switched after every ``intervl``-th one, cycling
back to the first picture when it ran out. Expressed per trial (1-based) that is
simply ``((trial - 1) // every_n) % n_images``: trials 1..N show picture 0,
N+1..2N picture 1, and so on, wrapping around.

Everything here is decided *before* the participant presses Begin -- which picture
goes with which trial, in which order -- so the experiment loop never makes a
choice (or touches the disk) at the moment a trial starts. That is the
performance lesson from MATLAB, which ran ``imread`` inside the response callback.

A background "source" is either a picture file path or :data:`CALM_GRADIENT`, the
built-in default that :mod:`emognition.imaging` renders at runtime (so it is
pixel-exact for any screen and needs no file).
"""

from __future__ import annotations

import os
import random
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# The built-in default background. Not a file: rendered by emognition.imaging.
CALM_GRADIENT = "builtin:calm-gradient"

# MATLAB's "Pics Interval [1-20]" field: values outside 1..20 fell back to 5.
MIN_EVERY_N = 1
MAX_EVERY_N = 20
DEFAULT_EVERY_N = 5

# Picture formats we accept. MATLAB listed '*.BMP','*.JPEG','*.JPG','*.PNG','*.GIF'
# with Windows-only, upper-case patterns (so lower-case files were missed on
# macOS/Linux); here the match is case-insensitive on every OS.
PICTURE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
)

# Setting values with a special meaning (anything else is a file/folder path).
SPEC_DEFAULT = "default"
SPEC_NONE = "none"
SPEC_SLIDESHOW = "slideshow"


def clamp_every_n(every_n: int) -> int:
    """Clamp a "change every N trials" value to MATLAB's valid range (1..20)."""
    return max(MIN_EVERY_N, min(MAX_EVERY_N, int(every_n)))


def slideshow_index(trial: int, every_n: int, n_images: int) -> int:
    """0-based picture index for a 1-based *trial* number.

    >>> [slideshow_index(t, 2, 3) for t in range(1, 9)]
    [0, 0, 1, 1, 2, 2, 0, 0]
    """
    if n_images < 1:
        raise ValueError("a slideshow needs at least one picture")
    if trial < 1:
        raise ValueError(f"trial numbers start at 1, got {trial}")
    return ((trial - 1) // clamp_every_n(every_n)) % n_images


def is_picture_file(path: str) -> bool:
    """True if *path* has a supported picture extension (any letter case)."""
    return os.path.splitext(path)[1].lower() in PICTURE_EXTENSIONS


def _natural_key(name: str) -> list:
    """Sort key so 'pic2' comes before 'pic10' (humans number files that way)."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name.lower())]


def list_pictures(*folders: str) -> list[str]:
    """All picture files in *folders* (not recursive), each folder sorted naturally.

    Folders are listed in the order given; hidden files and missing folders are
    skipped quietly, so a fresh install with no personal pictures still works.
    """
    found: list[str] = []
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        names = [
            n for n in os.listdir(folder)
            if not n.startswith(".") and is_picture_file(n)
            and os.path.isfile(os.path.join(folder, n))
        ]
        found.extend(os.path.join(folder, n) for n in sorted(names, key=_natural_key))
    return found


def friendly_name(source: str) -> str:
    """A human label for a background source.

    ``"03-rolling-hills.jpg"`` -> ``"Rolling hills"`` (a leading number used for
    ordering is dropped; dashes/underscores become spaces).
    """
    if source == CALM_GRADIENT:
        return "Calm gradient"
    stem = os.path.splitext(os.path.basename(source))[0]
    label = re.sub(r"^\d+[-_ ]+", "", stem)
    label = re.sub(r"[-_]+", " ", label).strip()
    if not label:
        return stem
    return label[0].upper() + label[1:]


@dataclass(frozen=True, slots=True)
class BackgroundPlan:
    """The pictures for a session, in display order, and how often they change.

    ``sources`` empty  -> plain window colour (no picture at all).
    One source         -> that picture for the whole session (the default).
    Several sources    -> a slideshow, switching every ``every_n`` trials.
    """

    sources: tuple[str, ...] = (CALM_GRADIENT,)
    every_n: int = DEFAULT_EVERY_N
    shuffled: bool = False

    @property
    def is_plain(self) -> bool:
        return not self.sources

    @property
    def is_slideshow(self) -> bool:
        return len(self.sources) > 1

    @property
    def first(self) -> str | None:
        """The picture shown on the Begin screen and the first trial."""
        return self.sources[0] if self.sources else None

    def source_for_trial(self, trial: int) -> str | None:
        """The picture to show during 1-based *trial* (None for a plain window)."""
        if not self.sources:
            return None
        return self.sources[slideshow_index(trial, self.every_n, len(self.sources))]

    def next_change_after(self, trial: int, n_trials: int) -> int | None:
        """The first trial after *trial* that shows a different picture, if any.

        Used to decode the upcoming picture in the background while the current
        one is on screen.
        """
        if not self.is_slideshow:
            return None
        n = clamp_every_n(self.every_n)
        nxt = ((trial - 1) // n + 1) * n + 1        # first trial of the next block
        while nxt <= n_trials:
            if self.source_for_trial(nxt) != self.source_for_trial(trial):
                return nxt
            nxt += n
        return None

    def describe(self) -> str:
        """One line for the session report, e.g. 'Slideshow: 6 pictures, every 5 trials, shuffled'."""
        if self.is_plain:
            return "None (plain)"
        if not self.is_slideshow:
            return friendly_name(self.sources[0])
        order = "shuffled" if self.shuffled else "in order"
        every = "every trial" if self.every_n == 1 else f"every {self.every_n} trials"
        return f"Slideshow: {len(self.sources)} pictures, {every}, {order}"


def plan_backgrounds(
    sources: Sequence[str],
    *,
    every_n: int = DEFAULT_EVERY_N,
    shuffle: bool = True,
    rng: random.Random | None = None,
) -> BackgroundPlan:
    """Build a plan from candidate pictures, shuffling once if asked.

    Like MATLAB (``S.picsshuffled = xtemp(randperm(...))``) the order is shuffled
    once up front and then cycled; pass a seeded *rng* for a reproducible order.
    """
    ordered = list(sources)
    if shuffle and len(ordered) > 1:
        (rng or random.Random()).shuffle(ordered)
    return BackgroundPlan(
        sources=tuple(ordered),
        every_n=clamp_every_n(every_n),
        shuffled=shuffle and len(ordered) > 1,
    )


def resolve_background(
    spec: str | None,
    *,
    picture_folders: Iterable[str] = (),
    every_n: int = DEFAULT_EVERY_N,
    shuffle: bool = True,
    rng: random.Random | None = None,
) -> BackgroundPlan:
    """Turn a background setting into a plan.

    ``spec`` is ``"default"`` (the calm gradient), ``"none"`` (plain window),
    ``"slideshow"`` (every picture in *picture_folders*), a picture file (shown
    for the whole session) or a folder (a slideshow of that folder).

    Raises:
        ValueError: with a message fit for the experimenter, if the path doesn't
            exist, isn't a supported picture, or a slideshow has no pictures.
            Failing before the window opens beats silently showing something else.
    """
    value = (spec or SPEC_DEFAULT).strip()
    key = value.lower()
    if key == SPEC_DEFAULT:
        return BackgroundPlan()
    if key == SPEC_NONE:
        return BackgroundPlan(sources=())
    if key == SPEC_SLIDESHOW:
        pictures = list_pictures(*picture_folders)
        if not pictures:
            raise ValueError("Slideshow selected, but no background pictures were found.")
        return plan_backgrounds(pictures, every_n=every_n, shuffle=shuffle, rng=rng)
    if os.path.isdir(value):
        pictures = list_pictures(value)
        if not pictures:
            raise ValueError(f"No pictures found in background folder: {value}")
        return plan_backgrounds(pictures, every_n=every_n, shuffle=shuffle, rng=rng)
    if os.path.isfile(value):
        if not is_picture_file(value):
            raise ValueError(f"Not a supported picture (png/jpg/bmp/gif/webp): {value}")
        return BackgroundPlan(sources=(value,), every_n=clamp_every_n(every_n))
    raise ValueError(f"Background picture or folder not found: {value}")
