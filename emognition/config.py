# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Experiment settings: the data the config screen collects, UI-free + testable.

The experimenter config window (PyQt6) edits an :class:`ExperimentSettings`, then
launches the experiment in a *separate process* via ``to_argv()`` -- which keeps
Qt and the pyglet experiment window out of each other's process (they crash if
they share one). Settings also persist to JSON ("keep previous settings").
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

# The five emotion tags, default = all selected.
ALL_EMOTION_TAGS: tuple[str, ...] = ("hap", "sca", "neu", "sad", "ang")

# Default playback volume (the experimenter sets this; not a participant control).
DEFAULT_VOLUME = 0.8


@dataclass(slots=True)
class ExperimentSettings:
    """Everything the experimenter sets before a Test session."""

    participant: str = "Participant01"
    experimenter: str = "APPstaff"
    audio_dir: str = ""          # "" -> use the bundled stimuli
    save_dir: str = ""           # "" -> default (./save_location)
    caption: str = "none"        # none | english | mandarin
    fullscreen: bool = False
    screen: int = 0              # display index for the experiment window
    shuffle: bool = True
    allow_replays: bool = False
    amp_visualizer: bool = False
    volume: float = DEFAULT_VOLUME
    emotions: list[str] = field(default_factory=lambda: list(ALL_EMOTION_TAGS))

    def to_argv(self) -> list[str]:
        """Build the ``emognition`` CLI arguments to run a session with these."""
        argv = [
            "--participant", self.participant,
            "--experimenter", self.experimenter,
            "--caption", self.caption,
        ]
        if self.audio_dir:
            argv += ["--audio-dir", self.audio_dir]
        if self.save_dir:
            argv += ["--save-dir", self.save_dir]
        if self.fullscreen:
            argv.append("--fullscreen")
        if self.screen:
            argv += ["--screen", str(self.screen)]
        if not self.shuffle:
            argv.append("--no-shuffle")
        if self.allow_replays:
            argv.append("--allow-replays")
        if self.amp_visualizer:
            argv.append("--amp-visualizer")
        if self.volume != DEFAULT_VOLUME:
            argv += ["--volume", f"{self.volume:.2f}"]
        # Only pass an explicit subset if it isn't the full set (order-insensitive).
        if set(self.emotions) != set(ALL_EMOTION_TAGS):
            argv += ["--emotions", ",".join(self.emotions)]
        return argv

    def save(self, path: str) -> str:
        """Persist to a JSON file; return the path."""
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "ExperimentSettings":
        """Load from JSON, ignoring unknown/missing keys (forward-compatible)."""
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        fields = {f for f in cls.__slots__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in fields})
