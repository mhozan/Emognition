# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Listening to a clip from the Calibration window.

Audio never runs in the Qt process (see ui/calibration_window.py): the first
:meth:`AuditionPlayer.play` starts ``emognition --audition``, a helper process
that opens PsychoPy's audio stream once -- that takes a second or two -- and
then plays each clip it is sent at once. It plays exactly as a session does:
one reusable stereo stream, at the session's Volume, so what the experimenter
hears is what a participant will hear.

The helper owns the audio device (exclusive ALSA, on Linux), so it is shut
down before the SPL tone, which needs the device to itself, and when the
Calibration window closes.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from ..io.lines import LineBuffer
from .assets import self_command


class AuditionPlayer(QObject):
    """One helper process and one audio stream, for the Calibration window."""

    starting = pyqtSignal()               # the helper is opening the audio stream
    playing = pyqtSignal(str, float)      # path, duration in seconds
    finished = pyqtSignal(str)            # the clip played to its end
    stopped = pyqtSignal(str)             # Stop, before the end
    failed = pyqtSignal(str)              # a message for the experimenter

    def __init__(self, volume: float, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._volume = max(0.0, min(1.0, volume))
        self._proc: QProcess | None = None
        self._ready = False
        self._pending: str | None = None  # asked for before the helper was ready
        self._closing = False
        self._out = LineBuffer()
        self._err = b""

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    @property
    def ready(self) -> bool:
        return self.running and self._ready

    def play(self, path: str) -> None:
        """Play *path* (starting the helper first if need be)."""
        if not self.running:
            self._start()
        if self._ready:
            self._send(f"play {path}")
        else:
            self._pending = path

    def stop(self) -> None:
        self._pending = None
        if self.ready:
            self._send("stop")

    def shutdown(self, wait_ms: int = 2000) -> None:
        """End the helper (it frees the audio device); waits up to *wait_ms*."""
        self._pending = None
        proc, self._proc, self._ready = self._proc, None, False
        if proc is None or proc.state() == QProcess.ProcessState.NotRunning:
            return
        self._closing = True
        proc.write(b"quit\n")
        proc.closeWriteChannel()
        if not proc.waitForFinished(wait_ms):
            proc.kill()
            proc.waitForFinished(500)
        self._closing = False

    # -- the helper process ----------------------------------------------------

    def _start(self) -> None:
        cmd = self_command(["--audition", "--volume", f"{self._volume:.2f}"])
        proc = QProcess(self)
        proc.setProgram(cmd[0])
        proc.setArguments(cmd[1:])
        proc.readyReadStandardOutput.connect(self._on_output)
        proc.readyReadStandardError.connect(self._on_error_output)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_process_error)
        self._proc, self._ready, self._out, self._err = proc, False, LineBuffer(), b""
        proc.start()
        self.starting.emit()

    def _send(self, line: str) -> None:
        if self._proc is not None:
            self._proc.write((line + "\n").encode("utf-8"))

    def _on_output(self) -> None:
        if self._proc is None:
            return
        for line in self._out.feed(bytes(self._proc.readAllStandardOutput())):
            line = line.strip()
            if line.startswith("{"):                 # PTB prints its own lines too
                try:
                    self._on_event(json.loads(line))
                except ValueError:
                    continue

    def _on_event(self, event: dict) -> None:
        status = event.get("status")
        if status == "ready":
            self._ready = True
            if self._pending:
                path, self._pending = self._pending, None
                self._send(f"play {path}")
        elif status == "playing":
            self.playing.emit(str(event.get("path", "")), float(event.get("duration") or 0.0))
        elif status == "finished":
            self.finished.emit(str(event.get("path", "")))
        elif status == "stopped":
            self.stopped.emit(str(event.get("path", "")))
        elif status == "error":
            self.failed.emit(str(event.get("message") or "Playback failed."))

    def _on_error_output(self) -> None:
        if self._proc is not None:
            self._err = (self._err + bytes(self._proc.readAllStandardError()))[-2000:]

    def _on_finished(self, code: int, _status) -> None:
        if self.sender() is not self._proc:          # an old helper, already replaced
            return
        self._proc, self._ready, self._pending = None, False, None
        if not self._closing and code != 0:
            tail = self._err.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
            self.failed.emit(f"The player stopped (exit {code}). {tail[0]}".strip())

    def _on_process_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart and self.sender() is self._proc:
            self._proc, self._ready, self._pending = None, False, None
            self.failed.emit("The player could not start.")
