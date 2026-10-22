"""
This file is part of Simisa.

Copyright (C) 2026 Peter Grønbæk Andersen <peter@grnbk.io>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import inspect
from typing import Callable, Optional


ProgressCallback = Callable[[str, float], None]


class ProgressReporter:
    """
    Manage progress reporting for read and write operations.

    Progress is represented as a float between 0.0 and 1.0. Callback
    invocation is throttled according to the configured progress interval.
    A callback is also triggered when the progress message changes.

    Args:
        callback: Function called with a progress message and a progress value
            between 0.0 and 1.0. If None, progress reporting is disabled.
        interval: Minimum progress change required between callbacks with the
            same message. Defaults to 0.01.

    Raises:
        TypeError: If callback is not callable or None, or if interval is not
            a float or int.
        ValueError: If interval is outside the range 0.0 to 1.0.
    """
    def __init__(self, callback: Optional[ProgressCallback] = None, interval: float = 0.01):
        if callback is not None:
            if not callable(callback):
                raise TypeError(
                    "Parameter 'callback' must be callable or None, "
                    f"but got {type(callback).__name__}"
                )

            try:
                signature = inspect.signature(callback)
            except (TypeError, ValueError) as exc:
                raise TypeError(
                    "Parameter 'callback' must have an inspectable signature"
                ) from exc

            try:
                signature.bind("message", 0.0)
            except TypeError as exc:
                raise TypeError(
                    "Parameter 'callback' must accept two positional arguments: "
                    "message and progress"
                ) from exc

        if not isinstance(interval, (int, float)):
            raise TypeError(
                "Parameter 'interval' must be float or int, "
                f"but got {type(interval).__name__}"
            )

        if not 0.0 <= interval <= 1.0:
            raise ValueError(
                f"Parameter 'interval' must be between 0.0 and 1.0, but got {interval}"
            )

        self.callback = callback
        self.interval = float(interval)
        self._last_progress: Optional[float] = None
        self._last_message: Optional[str] = None

    def report(self, message: str, current_bytes: int, total_bytes: int) -> None:
        """
        Report the current progress of an operation.

        The callback is triggered when this is the first report, the message
        changes, progress advances by at least the configured interval, or
        progress reaches 1.0.

        Progress is calculated from current_bytes and total_bytes and clamped
        to the range 0.0 to 1.0. If total_bytes is zero or negative, progress
        is reported as 0.0.

        Args:
            message: Human-readable description of the current operation.
            current_bytes: Number of bytes processed so far.
            total_bytes: Total number of bytes in the operation.

        Raises:
            TypeError: If message is not a string.
        """
        if self.callback is None:
            return

        if not isinstance(message, str):
            raise TypeError(
                f"Parameter 'message' must be str, but got {type(message).__name__}"
            )

        if total_bytes <= 0:
            progress = 0.0
        else:
            progress = current_bytes / total_bytes
            progress = max(0.0, min(1.0, progress))

        should_report = (
            self._last_progress is None
            or message != self._last_message
            or progress >= 1.0
            or progress - self._last_progress >= self.interval
        )

        if not should_report:
            return

        self.callback(message, progress)

        self._last_progress = progress
        self._last_message = message

    def complete(self, message: str = "Finished") -> None:
        """
        Report that the operation has completed.

        Reports progress as 1.0 regardless of the last calculated byte
        progress. An identical completion report is not emitted more than
        once.

        Args:
            message: Human-readable completion message. Defaults to "Finished".

        Raises:
            TypeError: If message is not a string.
        """
        if self.callback is None:
            return

        if not isinstance(message, str):
            raise TypeError(
                f"Parameter 'message' must be str, but got {type(message).__name__}"
            )

        if self._last_progress == 1.0 and self._last_message == message:
            return

        self.callback(message, 1.0)

        self._last_progress = 1.0
        self._last_message = message