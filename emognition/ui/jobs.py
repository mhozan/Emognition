# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2014-2026 Mohsen Hozan
#
# This file is part of Emognition. It is free software: you can redistribute
# it and/or modify it under the terms of the GNU Affero General Public License
# as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version. See the LICENSE file.

"""Background work for the Calibration window, without freezing it.

Reading and measuring a folder of recordings takes from milliseconds to
minutes; on the GUI thread even a short stall shows as a busy pointer. A
:class:`Job` runs one function on a Qt thread pool and reports back through
signals. The Job object lives on the GUI thread, so Qt delivers every signal
there as a queued call: widgets are only ever touched from the GUI thread.

The function receives the job itself, to say how far it has got
(:meth:`Job.report`), to hand over results one at a time as they are ready
(:meth:`Job.deliver` -- a gallery can fill in while the rest is computed), and
to notice :attr:`Job.cancelled` between files.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal


class Job(QObject):
    """One function, run on a thread pool, reporting back on the GUI thread."""

    progress = pyqtSignal(int, int)      # done, total
    item = pyqtSignal(object)            # one result of many, as soon as it's ready
    done = pyqtSignal(object)            # the function's return value
    failed = pyqtSignal(str)

    def __init__(self, fn: Callable[["Job"], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn
        self.cancelled = False
        self.finished = False

    def start(self, pool: QThreadPool) -> "Job":
        pool.start(_Runner(self))
        return self

    def cancel(self) -> None:
        """Ask the function to stop at its next check (it finishes the file it's on)."""
        self.cancelled = True

    def report(self, done: int, total: int) -> None:
        self.progress.emit(done, total)

    def deliver(self, item: object) -> None:
        self.item.emit(item)

    def _run(self) -> None:
        try:
            result = self._fn(self)
        except Exception as exc:  # noqa: BLE001 -- reported to the experimenter
            self.finished = True
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.finished = True
            self.done.emit(result)


class _Runner(QRunnable):
    """The pool's handle on a Job (Qt deletes it when it has run)."""

    def __init__(self, job: Job) -> None:
        super().__init__()
        self._job = job

    def run(self) -> None:  # noqa: D401 -- Qt's name
        self._job._run()
