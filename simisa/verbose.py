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

from enum import IntEnum
from typing import Optional, Union, Callable, Any


class VerbosityLevel(IntEnum):
    """
    Verbosity levels for SIMISA operations.

    SILENT (0): No verbose output (default).
    NORMAL (1): High-level operations (file opening, headers, subheaders, top-level blocks, include handling).
    DETAILED (2): Sub-blocks, element counts, block sizes, verification, skipped blocks.
    DEBUG (3): Low-level STF tokens, individual values read/written, offsets.
    """
    SILENT = 0
    NORMAL = 1
    DETAILED = 2
    DEBUG = 3


_global_verbosity: VerbosityLevel = VerbosityLevel.SILENT
_verbose_output: Optional[Union[Callable[[str], Any], Any]] = None


def normalize_verbosity(verbose: Union[bool, int, VerbosityLevel, None]) -> VerbosityLevel:
    """Normalize a verbose argument to a VerbosityLevel enum."""
    if verbose is None:
        return get_global_verbosity()
    if isinstance(verbose, bool):
        return VerbosityLevel.NORMAL if verbose else VerbosityLevel.SILENT
    if isinstance(verbose, VerbosityLevel):
        return verbose
    if isinstance(verbose, int):
        if verbose <= 0:
            return VerbosityLevel.SILENT
        elif verbose == 1:
            return VerbosityLevel.NORMAL
        elif verbose == 2:
            return VerbosityLevel.DETAILED
        else:
            return VerbosityLevel.DEBUG
    if isinstance(verbose, str):
        key = verbose.strip().upper()
        if hasattr(VerbosityLevel, key):
            return getattr(VerbosityLevel, key)
        raise ValueError(f"Unknown verbosity level: {verbose}")
    return VerbosityLevel.SILENT


def get_global_verbosity() -> VerbosityLevel:
    """Get the current global verbosity level."""
    return _global_verbosity


def set_global_verbosity(level: Union[bool, int, VerbosityLevel]) -> None:
    """Set the global verbosity level."""
    global _global_verbosity
    _global_verbosity = normalize_verbosity(level)


def get_verbose_output():
    """Get the output target for verbose messages (None = print to stdout)."""
    return _verbose_output


def set_verbose_output(target: Optional[Union[Callable[[str], Any], Any]]) -> None:
    """Set the output target (callable, file-like object with write(), or None for print)."""
    global _verbose_output
    _verbose_output = target


def verbose_print(
    category: str,
    message: str,
    level: VerbosityLevel = VerbosityLevel.NORMAL,
    current_level: Optional[VerbosityLevel] = None,
) -> None:
    """
    Emit a formatted verbose message if active verbosity level is >= level.
    """
    active_level = current_level if current_level is not None else get_global_verbosity()
    if active_level >= level:
        text = f"[simisa:{category}] {message}"
        out = get_verbose_output()
        if callable(out):
            out(text)
        elif hasattr(out, "write"):
            out.write(text + "\n")
            if hasattr(out, "flush"):
                out.flush()
        else:
            print(text)
