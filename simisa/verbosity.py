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

import logging
from typing import Optional, Union


Verbose = Optional[Union[bool, int]]


def normalize_verbosity(verbose: Verbose) -> Optional[int]:
    """
    Normalize a verbose argument to a logging level.

    Args:
        verbose (Verbose):
            False or None: Disable verbose output.
            True: Enable INFO-level verbose output.
            logging.INFO: Enable INFO-level verbose output.
            logging.DEBUG: Enable DEBUG-level verbose output.

    Returns:
        The corresponding logging level, or None if verbose output is disabled.

    Raises:
        ValueError: If an unsupported logging level is supplied.
        TypeError: If verbose is not a bool, int, or None.
    """
    if verbose is None or verbose is False:
        return None

    if verbose is True:
        return logging.INFO

    if not isinstance(verbose, int):
        raise TypeError(
            "Parameter 'verbose' must be a bool, logging.INFO, logging.DEBUG, "
            f"or None, but got {type(verbose).__name__}"
        )

    if verbose not in (logging.INFO, logging.DEBUG):
        raise ValueError(
            "Parameter 'verbose' must be logging.INFO or logging.DEBUG, "
            f"but got {verbose}"
        )

    return verbose


def verbosity_enabled(verbosity: Optional[int], level: int = logging.INFO) -> bool:
    """
    Check whether a logging level is enabled by the current verbosity.

    Args:
        verbosity (Optional[int]): Current verbosity level as a logging level,
            or None if verbose output is disabled.
        level (int): Logging level to check. Defaults to logging.INFO.

    Returns:
        bool: True if the requested logging level is enabled by the current
        verbosity, otherwise False.
    """
    return verbosity is not None and verbosity <= level
