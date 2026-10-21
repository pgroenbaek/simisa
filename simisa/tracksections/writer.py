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

import math

from .. import TokenID
from ..format import BlockFormat
from ..writer import BlockWriter
from ..verbosity import Verbose
from .models import *


TRACKSECTION_BLOCK = BlockFormat(
    newline_after_start=True,
    newline_before_closing=True
)


def write_local_tracksections(writer: BlockWriter, tracksections: TrackSections, write_max_sections: bool = True) -> None:
    """
    Write local track sections to a BlockWriter.

    Writes the `TrackSection` sub-blocks and their child blocks.

    Args:
        writer (BlockWriter): Writer to write the local track sections to.
        tracksections (TrackSections): Track sections object containing the
            maximum section index and track section objects. 
        write_max_sections (bool): Whether to write the maximum section index. Defaults to True.
    """
    if not isinstance(tracksections, TrackSections):
        raise TypeError(f"DynTrackObj property 'track_sections' must be TrackSections, but got {type(tracksections).__name__}")

    for section_index, tracksection in tracksections.track_sections.items():
        if not isinstance(tracksection, TrackSection):
            raise TypeError(f"TrackSections property 'track_sections' must contain TrackSection objects, but got {type(tracksection).__name__}")

    if write_max_sections:
        writer.write_uint(tracksections.max_section_index)

    for section_index, tracksection in sorted(tracksections.track_sections.items()):
        with writer.sub_block(TokenID.TrackSection, block_format=TRACKSECTION_BLOCK) as tracksection_block:
            with tracksection_block.sub_block(TokenID.SectionCurve) as sectioncurve_block:
                sectioncurve_block.write_int(0)

            tracksection_block.write_uint(tracksection.section_index)

            if tracksection.section_size is not None:
                tracksection_block.write_float(tracksection.section_size.length)
                tracksection_block.write_float(0.0)
            
            elif tracksection.section_curve is not None:
                tracksection_block.write_float(math.radians(tracksection.section_curve.angle))
                tracksection_block.write_float(tracksection.section_curve.radius)
