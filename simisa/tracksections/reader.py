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
import logging
from typing import List

from .. import TokenID
from ..reader import BlockReader
from ..header import SimisaSubheaderError
from ..progress import ProgressCallback
from ..verbosity import Verbose
from .models import *

logger = logging.getLogger(__name__)



def load(
    filepath: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> TSection:
    """
    Load and parse a tsection file from disk (both local/global tsection.dat).

    It opens the file at the given path, validates that it is a supported tsection
    file based on its subheader, and returns a parsed TSection object.

    This function supports loading custom tsection extensions in the same way that
    Open Rails does. Track shape/section data is merged and the max shape/section
    index is set to the highest value found.

    Args:
        filepath (str): Path to the tracksections file.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        TSection: The parsed tracksections object.

    Raises:
        TypeError: If a parameter is not of the expected type.
        SimisaHeaderError: If the data has an invalid or unrecognized SIMISA header.
        SimisaSubheaderError: If the data has an invalid or unrecognized SIMISA subheader.
        BlockReaderError: If the block reader encounters an error or malformed data.
        StfReaderError: If the STF reader encounters an error or malformed data.
        UnresolvableIncludeError: If includes within the file cannot be resolved.
        OSError: If the file cannot be opened.
    """
    if not isinstance(filepath, str):
        raise TypeError(f"Parameter 'filepath' must be str, but got {type(filepath).__name__}")

    with BlockReader.open(filepath, progress=progress, verbose=verbose) as reader:

        if reader.filetype not in ('F', 'T'):
            raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a tsection file?")

        return read_tsection(reader)


def loads(
    tsection_text: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> TSection:
    """
    Parse tracksections from a string containing tsection data (both local/global tsection.dat).

    This function reads tracksections data from the provided string, validates
    that it represents a supported tracksections file based on its subheader, and
    returns a parsed TSection object.

    If you want to load custom tsection extensions with this function you need to use
    the `simisa.resolve_includes` function beforehand to resolve includes manually.

    Args:
        tsection_text (str): String containing tracksections file data.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        TSection: The parsed tracksections object.

    Raises:
        TypeError: If a parameter is not of the expected type.
        SimisaHeaderError: If the data has an invalid or unrecognized SIMISA header.
        SimisaSubheaderError: If the data has an invalid or unrecognized SIMISA subheader.
        BlockReaderError: If the block reader encounters an error or malformed data.
        StfReaderError: If the STF reader encounters an error or malformed data.
        UnresolvableIncludeError: If includes within the file cannot be resolved.
    """
    if not isinstance(tsection_text, str):
        raise TypeError(f"Parameter 'tsection_text' must be str, but got {type(tsection_text).__name__}")

    reader = BlockReader.from_string(tsection_text, progress=progress, verbose=verbose)

    if reader.filetype not in ('F', 'T'):
        raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a tsection file?")

    return read_tsection(reader)


def read_tsection(reader: BlockReader) -> TSection:
    """
    Read and parse a tsection file from a BlockReader.

    Consumes the `TrackSections`, `TrackShapes`, and `SectionIdx` sub-blocks
    and their child blocks, returning a fully constructed TSection object.
    
    When multiple top-level blocks with the same token ID are present, their items are merged and the max
    shape/section index is set to the highest value found. This allows for loading data from
    custom tsection extensions in the same way that Open Rails does.

    Args:
        reader (BlockReader): Reader positioned at the start of a tsection file.

    Returns:
        TSection: The parsed tsection file.
    """
    tsection = TSection()

    for sub_block in reader:
        if sub_block.id == TokenID.TrackSections:
            if reader.filetype == 'F': # global tsection.dat
                if tsection.tracksections is None:
                    tsection.tracksections = read_global_tracksections(sub_block)
                else:
                    tsection.tracksections += read_global_tracksections(sub_block)
            
            elif reader.filetype == 'T': # local tsection.dat
                if tsection.tracksections is None:
                    tsection.tracksections = read_local_tracksections(sub_block)
                else:
                    tsection.tracksections += read_local_tracksections(sub_block)
        
        elif sub_block.id == TokenID.TrackShapes:
            if tsection.trackshapes is None:
                tsection.trackshapes = read_trackshapes(sub_block)
            else:
                tsection.trackshapes += read_trackshapes(sub_block)
        
        elif sub_block.id == TokenID.SectionIdx:
            if tsection.sectionidx is None:
                tsection.sectionidx = read_tsectionidx(sub_block)
            else:
                tsection.sectionidx += read_tsectionidx(sub_block)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return tsection



def read_global_tracksections(reader: BlockReader) -> TrackSections:
    """
    Read and parse track sections from a BlockReader.

    Consumes the `TrackSections` block and returns a TrackSections object.

    Args:
        reader (BlockReader): Reader positioned at a track sections block.

    Returns:
        TrackSections: The parsed track sections.
    """
    reader.report_progress("Reading track sections...")

    reader.verify_id(TokenID.TrackSections)

    tracksections = TrackSections()
    tracksections.max_section_index = reader.read_uint()

    for tracksection_block in reader:
        tracksection_block.verify_id(TokenID.TrackSection)

        section_index = tracksection_block.read_uint()
        section_curve = None
        section_size = None
        section_skew = None
        water_scoop = False

        for sub_block in tracksection_block:
            if sub_block.id == TokenID.SectionCurve:
                section_curve = read_section_curve(sub_block)
            
            elif sub_block.id == TokenID.SectionSize:
                section_size = read_section_size(sub_block)

            elif sub_block.id == TokenID.SectionSkew:
                section_skew = read_section_skew(sub_block)

            elif sub_block.id == TokenID.WaterScoop:
                water_scoop = True
            
            else:
                logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
                sub_block.skip()

        tracksection = TrackSection(
            section_index=section_index,
            section_curve=section_curve,
            section_size=section_size,
            section_skew=section_skew,
            water_scoop=water_scoop
        )
        tracksections.add_section(tracksection)
        
    return tracksections


def read_local_tracksections(reader: BlockReader, read_max_sections: bool = True) -> TrackSections:
    """
    Read and parse track sections from a BlockReader.

    Consumes the `TrackSections` block and returns a TrackSections object.

    Args:
        reader (BlockReader): Reader positioned at a track sections block.
        read_max_sections (bool): Whether to read the maximum section index. Defaults to True.

    Returns:
        TrackSections: The parsed track sections.
    """
    reader.report_progress("Reading track sections...")

    reader.verify_id(TokenID.TrackSections)

    tracksections = TrackSections()

    if read_max_sections:
        tracksections.max_section_index = reader.read_uint()

    for tracksection_block in reader:
        tracksection_block.verify_id(TokenID.TrackSection)

        with tracksection_block.sub_block(TokenID.SectionCurve) as section_curve_block:
            section_curve_block.read_int()

        section_index = tracksection_block.read_uint()
        a = tracksection_block.read_float()
        b = tracksection_block.read_float()

        if b == 0: # straight
            section_size = SectionSize(length=a)
            tracksection = RouteTrackSection(
                section_index=section_index,
                section_curve=None,
                section_size=section_size
            )
        else: # curved
            section_curve = SectionCurve(radius=b, angle=math.degrees(a))
            tracksection = RouteTrackSection(
                section_index=section_index,
                section_curve=section_curve,
                section_size=None
            )
        
        tracksections.add_section(tracksection)
        
    return tracksections


def read_section_curve(reader: BlockReader) -> SectionCurve:
    """
    Read and parse a section curve from a BlockReader.

    Consumes the `SectionCurve` sub-block and returns a SectionCurve object.

    Args:
        reader (BlockReader): Reader positioned at a section curve block.

    Returns:
        SectionCurve: The parsed section curve.
    """
    reader.verify_id(TokenID.SectionCurve)
    
    radius = reader.read_float()
    angle = reader.read_float()

    return SectionCurve(radius=radius, angle=angle)


def read_section_size(reader: BlockReader) -> SectionSize:
    """
    Read and parse a section size from a BlockReader.

    Consumes the `SectionSize` sub-block and returns a SectionSize object.

    Args:
        reader (BlockReader): Reader positioned at a section size block.

    Returns:
        SectionSize: The parsed section size.
    """
    reader.verify_id(TokenID.SectionSize)

    width = reader.read_float()
    length = reader.read_float()

    return SectionSize(width=width, length=length)


def read_section_skew(reader: BlockReader) -> SectionSkew:
    """
    Read and parse a section skew from a BlockReader.

    Consumes the `SectionSkew` sub-block and returns a SectionSkew object.

    Args:
        reader (BlockReader): Reader positioned at a section skew block.

    Returns:
        SectionSkew: The parsed section skew.
    """
    reader.verify_id(TokenID.SectionSkew)
    
    angle = reader.read_float()

    return SectionSkew(angle=angle)


def read_trackshapes(reader: BlockReader) -> TrackShapes:
    """
    Read and parse track shapes from a BlockReader.

    Consumes the `TrackShapes` block and returns a TrackShapes object.

    Args:
        reader (BlockReader): Reader positioned at a track shapes block.

    Returns:
        TrackShapes: The parsed track shapes.
    """
    reader.report_progress("Reading track shapes...")

    reader.verify_id(TokenID.TrackShapes)

    trackshapes = TrackShapes()
    trackshapes.max_section_index = reader.read_uint()

    for trackshape_block in reader:
        trackshape_block.verify_id(TokenID.TrackShape)

        shape_index = trackshape_block.read_uint()
        file_name = None
        num_paths = None
        main_route = None
        clearance_distance = 0.0
        section_idxs = None
        xover_pts = None
        tunnel_shape = False
        road_shape = False
        crossover_shape = False
        manual_junction_shape = False

        for sub_block in trackshape_block:
            if sub_block.id == TokenID.FileName:
                file_name = sub_block.read_string()
            
            elif sub_block.id == TokenID.NumPaths:
                num_paths = sub_block.read_uint()

            elif sub_block.id == TokenID.MainRoute:
                main_route = sub_block.read_uint()

            elif sub_block.id == TokenID.ClearanceDist:
                clearance_distance = sub_block.read_float()

            elif sub_block.id == TokenID.SectionIdx:
                if section_idxs is None:
                    section_idxs = []
                
                sectionidx = read_sectionidx(sub_block)
                section_idxs.append(sectionidx)

            elif sub_block.id == TokenID.XoverPts:
                xover_pts = read_xoverpts(sub_block)

            elif sub_block.id == TokenID.TunnelShape:
                tunnel_shape = True

            elif sub_block.id == TokenID.RoadShape:
                road_shape = True

            elif sub_block.id == TokenID.CrossoverShape:
                crossover_shape = True

            elif sub_block.id == TokenID.ManualJunctionShape:
                manual_junction_shape = True
            
            else:
                logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
                sub_block.skip()

        trackshape_block.verify_count(num_paths, len(section_idxs))

        trackshape = TrackShape(
            shape_index=shape_index,
            file_name=file_name,
            num_paths=num_paths,
            main_route=main_route,
            clearance_distance=clearance_distance,
            section_idxs=section_idxs,
            xover_pts=xover_pts,
            tunnel_shape=tunnel_shape,
            road_shape=road_shape,
            crossover_shape=crossover_shape,
            manual_junction_shape=manual_junction_shape
        )
        trackshapes.add_shape(trackshape)
        
    return trackshapes


def read_sectionidx(reader: BlockReader) -> SectionIdx:
    """
    Read and parse a section index block from a BlockReader.

    Consumes the `SectionIdx` block and returns a SectionIdx object.

    Args:
        reader (BlockReader): Reader positioned at a section index block.

    Returns:
        SectionIdx: The parsed section index.
    """
    reader.verify_id(TokenID.SectionIdx)

    track_sections: List[int] = []
    num_sections = reader.read_uint()

    x = reader.read_float()
    y = reader.read_float()
    z = reader.read_float()
    a = reader.read_float()

    for _ in range(num_sections):
        track_sections.append(reader.read_uint())
    
    reader.verify_count(num_sections, len(track_sections))

    return SectionIdx(
        x=x,
        y=y,
        z=z,
        a=a,
        track_sections=track_sections
    )


def read_xoverpts(reader: BlockReader) -> List[XoverPt]:
    """
    Read and parse an xover pts block from a BlockReader.

    Consumes the `XoverPts` block and returns a list of `XoverPt` objects.

    Args:
        reader (BlockReader): Reader positioned at an xover pts block.

    Returns:
        SectionIdx: The parsed xover pts.
    """
    reader.verify_id(TokenID.XoverPts)

    xover_pts: List[XoverPt] = []
    count = reader.read_uint()

    for xoverpt_block in reader:
        xoverpt_block.verify_id(TokenID.XoverPt)

        x = reader.read_float()
        y = reader.read_float()
        z = reader.read_float()

        xover_pts.append(XoverPt(
            x=x,
            y=y,
            z=z
        ))

    reader.verify_count(count, len(xover_pts))

    return xover_pts


def read_tsectionidx(reader: BlockReader) -> TSectionIdx:
    """
    Read and parse section index block containing track paths from a BlockReader.

    Consumes the `SectionIdx` block and returns a TSectionIdx object.

    Args:
        reader (BlockReader): Reader positioned at a section index block.

    Returns:
        TSectionIdx: The parsed track section indices.
    """
    reader.report_progress("Reading track paths...")

    reader.verify_id(TokenID.SectionIdx)

    tsectionidx = TSectionIdx()
    count = reader.read_uint()

    for trackpath_block in reader:
        trackpath_block.verify_id(TokenID.TrackPath)

        section_index = trackpath_block.read_uint()
        num_sections = trackpath_block.read_uint()
        track_sections: List[int] = []

        for _ in range(num_sections):
            track_sections.append(trackpath_block.read_uint())
        
        trackpath = TrackPath(
            section_index=section_index,
            track_sections=track_sections
        )
        tsectionidx.add_path(trackpath)
    
    reader.verify_count(count, len(tsectionidx.track_paths))

    return tsectionidx