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
from pathlib import Path
from typing import List

from .. import TokenID
from ..reader import BlockReader
from ..header import SimisaSubheaderError
from ..progress import ProgressCallback
from ..verbosity import Verbose
from ..tracksections.reader import read_local_tracksections
from .models import *

logger = logging.getLogger(__name__)



def load(
    filepath: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> World:
    """
    Load and parse a world file from disk.

    This function supports both compressed/uncompressed as well as binary/text data.
    It opens the file at the given path, validates that it is a supported world
    file based on its subheader, and returns a parsed World object.

    Args:
        filepath (str): Path to the world file.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        World: The parsed world object.

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

        if not reader.filetype == 'w':
            raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a world file?")

        world = read_world(reader)

        file_path = Path(filepath)

        if file_path.is_file():
            world.file_name = file_path.name

        return world


def loads(
    world_text: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> World:
    """
    Parse a world file from a string containing world data.

    This function does not support binary or compressed data. It reads world
    data from the provided string, validates that it represents a supported
    world file based on its subheader, and returns a parsed World object.

    Args:
        world_text (str): String containing world file data.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        World: The parsed world object.

    Raises:
        TypeError: If a parameter is not of the expected type.
        SimisaHeaderError: If the data has an invalid or unrecognized SIMISA header.
        SimisaSubheaderError: If the data has an invalid or unrecognized SIMISA subheader.
        BlockReaderError: If the block reader encounters an error or malformed data.
        StfReaderError: If the STF reader encounters an error or malformed data.
        UnresolvableIncludeError: If includes within the file cannot be resolved.
    """
    if not isinstance(world_text, str):
        raise TypeError(f"Parameter 'world_text' must be str, but got {type(world_text).__name__}")

    reader = BlockReader.from_string(world_text, progress=progress, verbose=verbose)

    if not reader.filetype == 'w':
        raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a world file?")

    return read_world(reader)


def read_world(reader: BlockReader) -> World:
    """
    Read and parse a worldfile block from a BlockReader.

    Consumes the `Tr_Worldfile` sub-block and its child blocks, returning a fully
    constructed World object.

    Args:
        reader (BlockReader): Reader positioned at a worldfile block.

    Returns:
        World: The parsed world file.
    """
    with reader.sub_block(TokenID.Tr_Worldfile) as worldfile_block:
        objects = read_world_objects(worldfile_block)

        return World(objects=objects)


def read_world_objects(reader: BlockReader) -> List[WorldObj]:
    """
    Read and parse world objects from a BlockReader.

    Consumes the `Tr_Worldfile` block and its child blocks, returning a list of WorldObj objects.

    Args:
        reader (BlockReader): Reader positioned at a world file block.

    Returns:
        List[WorldObj]: The parsed world objects.
    """
    reader.report_progress("Reading world objects...")
    
    reader.verify_id(TokenID.Tr_Worldfile)

    objects: List[WorldObj] = []
    current_watermark: int = 0

    for sub_block in reader:
        world_object = None

        if sub_block.id == TokenID.CollideObject:
            world_object = read_collide_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Static:
            world_object = read_static_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.TrackObj:
            world_object = read_track_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.CarSpawner:
            world_object = read_carspawner_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Siding:
            world_object = read_siding_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Platform:
            world_object = read_platform_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Forest:
            world_object = read_forest_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.LevelCr:
            world_object = read_levelcr_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Dyntrack:
            world_object = read_dyntrack_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Transfer:
            world_object = read_transfer_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Gantry:
            world_object = read_gantry_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Pickup:
            world_object = read_pickup_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Hazard:
            world_object = read_hazard_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Signal:
            world_object = read_signal_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Speedpost:
            world_object = read_speedpost_object(sub_block, current_watermark)
            sub_block.skip()

        elif sub_block.id == TokenID.Tr_Watermark:
            current_watermark = sub_block.read_int()
            sub_block.skip()

        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

        if world_object is not None:
            objects.append(world_object)

    reader.skip()

    return objects


def read_collide_object(reader: BlockReader, detail_level: int) -> StaticObj:
    """
    Read and parse a collide object from a BlockReader.

    Consumes the `CollideObject` block and its child blocks, returning a StaticObj object.

    Args:
        reader (BlockReader): Reader positioned at a collide object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        StaticObj: The parsed collide object.
    """
    reader.verify_id(TokenID.CollideObject)

    static_obj = StaticObj()
    static_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            static_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            static_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            static_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            static_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            static_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            static_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            static_obj.static_flags = sub_block.read_flags()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return static_obj


def read_static_object(reader: BlockReader, detail_level: int) -> StaticObj:
    """
    Read and parse a static object from a BlockReader.

    Consumes the `Static` block and its child blocks, returning a StaticObj object.

    Args:
        reader (BlockReader): Reader positioned at a static object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        StaticObj: The parsed static object.
    """
    reader.verify_id(TokenID.Static)

    static_obj = StaticObj()
    static_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            static_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            static_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            static_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            static_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            static_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            static_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            static_obj.static_flags = sub_block.read_flags()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return static_obj


def read_track_object(reader: BlockReader, detail_level: int) -> TrackObj:
    """
    Read and parse a track object from a BlockReader.

    Consumes the `TrackObj` block and its child blocks, returning a TrackObj object.

    Args:
        reader (BlockReader): Reader positioned at a track object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        TrackObj: The parsed track object.
    """
    reader.verify_id(TokenID.TrackObj)

    track_obj = TrackObj()
    track_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            track_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            track_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            track_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            track_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            track_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            track_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            track_obj.static_flags = sub_block.read_flags()

        elif sub_block.id == TokenID.SectionIdx:
            track_obj.section_index = sub_block.read_uint()

        elif sub_block.id == TokenID.Elevation:
            track_obj.elevation = sub_block.read_float()

        elif sub_block.id == TokenID.CollideFlags:
            track_obj.collide_flags = sub_block.read_flags()

        elif sub_block.id == TokenID.JNodePosn:
            track_obj.jnode_position = read_jnode_position(sub_block)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return track_obj


def read_carspawner_object(reader: BlockReader, detail_level: int) -> CarSpawnerObj:
    """
    Read and parse a car spawner object from a BlockReader.

    Consumes the `CarSpawner` block and its child blocks, returning a CarSpawnerObj object.

    Args:
        reader (BlockReader): Reader positioned at a car spawner object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        CarSpawnerObj: The parsed car spawner object.
    """
    reader.verify_id(TokenID.CarSpawner)

    carspawner_obj = CarSpawnerObj()
    carspawner_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            carspawner_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            carspawner_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            carspawner_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            carspawner_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            carspawner_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            carspawner_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            carspawner_obj.static_flags = sub_block.read_flags()

        elif sub_block.id == TokenID.CarFrequency:
            carspawner_obj.car_frequency = sub_block.read_float()

        elif sub_block.id == TokenID.CarAvSpeed:
            carspawner_obj.car_avg_speed = sub_block.read_float()

        elif sub_block.id == TokenID.ORTSListName:
            carspawner_obj.list_name = sub_block.read_string()

        elif sub_block.id == TokenID.TrItemId:
            if carspawner_obj.tr_item_ids is None:
                carspawner_obj.tr_item_ids = []
            
            tr_item_id = read_tr_item_id(sub_block)
            carspawner_obj.tr_item_ids.append(tr_item_id)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return carspawner_obj


def read_siding_object(reader: BlockReader, detail_level: int) -> SidingObj:
    """
    Read and parse a siding object from a BlockReader.

    Consumes the `Siding` block and its child blocks, returning a SidingObj object.

    Args:
        reader (BlockReader): Reader positioned at a siding object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        SidingObj: The parsed siding object.
    """
    reader.verify_id(TokenID.Siding)

    siding_obj = SidingObj()
    siding_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            siding_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            siding_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            siding_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            siding_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            siding_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            siding_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            siding_obj.static_flags = sub_block.read_flags()
        
        elif sub_block.id == TokenID.SidingData:
            siding_obj.siding_data = sub_block.read_flags()

        elif sub_block.id == TokenID.TrItemId:
            if siding_obj.tr_item_ids is None:
                siding_obj.tr_item_ids = []
            
            tr_item_id = read_tr_item_id(sub_block)
            siding_obj.tr_item_ids.append(tr_item_id)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return siding_obj


def read_platform_object(reader: BlockReader, detail_level: int) -> PlatformObj:
    """
    Read and parse a platform object from a BlockReader.

    Consumes the `Platform` block and its child blocks, returning a PlatformObj object.

    Args:
        reader (BlockReader): Reader positioned at a platform object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        PlatformObj: The parsed platform object.
    """
    reader.verify_id(TokenID.Platform)

    platform_obj = PlatformObj()
    platform_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            platform_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            platform_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            platform_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            platform_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            platform_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            platform_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            platform_obj.static_flags = sub_block.read_flags()
        
        elif sub_block.id == TokenID.PlatformData:
            platform_obj.platform_data = sub_block.read_flags()

        elif sub_block.id == TokenID.TrItemId:
            if platform_obj.tr_item_ids is None:
                platform_obj.tr_item_ids = []
            
            tr_item_id = read_tr_item_id(sub_block)
            platform_obj.tr_item_ids.append(tr_item_id)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return platform_obj


def read_forest_object(reader: BlockReader, detail_level: int) -> ForestObj:
    """
    Read and parse a forest object from a BlockReader.

    Consumes the `Forest` block and its child blocks, returning a ForestObj object.

    Args:
        reader (BlockReader): Reader positioned at a forest object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        ForestObj: The parsed forest object.
    """
    reader.verify_id(TokenID.Forest)

    forest_obj = ForestObj()
    forest_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            forest_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            forest_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            forest_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            forest_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            forest_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            forest_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            forest_obj.static_flags = sub_block.read_flags()
        
        elif sub_block.id == TokenID.TreeTexture:
            forest_obj.tree_texture = sub_block.read_string()
            
            if forest_obj.tree_texture is None:
                forest_obj.is_yard = True
        
        elif sub_block.id == TokenID.ScaleRange:
            minimum = sub_block.read_float()
            maximum = sub_block.read_float()

            forest_obj.scale_range = ScaleRange(
                minimum=minimum,
                maximum=maximum
            )
        
        elif sub_block.id == TokenID.Area:
            x = sub_block.read_float()
            z = sub_block.read_float()

            forest_obj.forest_area = ForestArea(
                x=x,
                z=z
            )
        
        elif sub_block.id == TokenID.Population:
            forest_obj.population = sub_block.read_int()
        
        elif sub_block.id == TokenID.TreeSize:
            width = sub_block.read_float()
            height = sub_block.read_float()

            forest_obj.tree_size = TreeSize(
                width=width,
                height=height
            )
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return forest_obj


def read_levelcr_object(reader: BlockReader, detail_level: int) -> LevelCrObj:
    """
    Read and parse a level crossing object from a BlockReader.

    Consumes the `LevelCr` block and its child blocks, returning a LevelCrObj object.

    Args:
        reader (BlockReader): Reader positioned at a level crossing object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        LevelCrObj: The parsed level crossing object.
    """
    reader.verify_id(TokenID.LevelCr)

    levelcr_obj = LevelCrObj()
    levelcr_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            levelcr_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            levelcr_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            levelcr_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            levelcr_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            levelcr_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            levelcr_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            levelcr_obj.static_flags = sub_block.read_flags()
        
        elif sub_block.id == TokenID.LevelCrParameters:
            warning_time = sub_block.read_float()
            minimum_distance = sub_block.read_float()

            levelcr_obj.levelcr_params = LevelCrParams(
                warning_time=warning_time,
                minimum_distance=minimum_distance
            )
        
        elif sub_block.id == TokenID.CrashProbability:
            levelcr_obj.crash_probability = sub_block.read_int()
        
        elif sub_block.id == TokenID.LevelCrData:
            data1 = sub_block.read_flags()
            data2 = sub_block.read_flags()
            visible = (data1 & 0x1) == 0
            silent = (not visible) or ((data1 & 0x6) == 0x6)

            levelcr_obj.levelcr_data = LevelCrData(
                data1=data1,
                data2=data2
            )
            levelcr_obj.visible = visible
            levelcr_obj.silent = silent
        
        elif sub_block.id == TokenID.LevelCrTiming:
            initial_timing = sub_block.read_float()
            serious_timing = sub_block.read_float()
            animation_timing = sub_block.read_float()

            levelcr_obj.levelcr_timing = LevelCrTiming(
                initial_timing=initial_timing,
                serious_timing=serious_timing,
                animation_timing=animation_timing
            )
        
        elif sub_block.id == TokenID.ORTSSoundFileName:
            levelcr_obj.sound_filename = sub_block.read_string()
        
        elif sub_block.id == TokenID.TrItemId:
            if levelcr_obj.tr_item_ids is None:
                levelcr_obj.tr_item_ids = []
            
            tr_item_id = read_tr_item_id(sub_block)
            levelcr_obj.tr_item_ids.append(tr_item_id)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return levelcr_obj


def read_dyntrack_object(reader: BlockReader, detail_level: int) -> DynTrackObj:
    """
    Read and parse a dynamic track object from a BlockReader.

    Consumes the `Dyntrack` block and its child blocks, returning a DynTrackObj object.

    Args:
        reader (BlockReader): Reader positioned at a dynamic track object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        DynTrackObj: The parsed dynamic track object.
    """
    reader.verify_id(TokenID.Dyntrack)

    dyntrack_obj = DynTrackObj()
    dyntrack_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            dyntrack_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.Position:
            dyntrack_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            dyntrack_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.VDbId:
            dyntrack_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            dyntrack_obj.static_flags = sub_block.read_flags()

        elif sub_block.id == TokenID.SectionIdx:
            dyntrack_obj.section_index = sub_block.read_uint()

        elif sub_block.id == TokenID.Elevation:
            dyntrack_obj.elevation = sub_block.read_float()

        elif sub_block.id == TokenID.CollideFlags:
            dyntrack_obj.collide_flags = sub_block.read_uint()
        
        elif sub_block.id == TokenID.TrackSections:
            dyntrack_obj.track_sections = read_local_tracksections(sub_block, read_max_sections=False)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return dyntrack_obj


def read_transfer_object(reader: BlockReader, detail_level: int) -> TransferObj:
    """
    Read and parse a transfer object from a BlockReader.

    Consumes the `Transfer` block and its child blocks, returning a TransferObj object.

    Args:
        reader (BlockReader): Reader positioned at a transfer object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        TransferObj: The parsed transfer object.
    """
    reader.verify_id(TokenID.Transfer)

    transfer_obj = TransferObj()
    transfer_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            transfer_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            transfer_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            transfer_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            transfer_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            transfer_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            transfer_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            transfer_obj.static_flags = sub_block.read_flags()

        elif sub_block.id == TokenID.Width:
            transfer_obj.width = sub_block.read_float()

        elif sub_block.id == TokenID.Height:
            transfer_obj.height = sub_block.read_float()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return transfer_obj


def read_gantry_object(reader: BlockReader, detail_level: int) -> GantryObj:
    """
    Read and parse a gantry object from a BlockReader.

    Consumes the `Gantry` block and its child blocks, returning a GantryObj object.

    Args:
        reader (BlockReader): Reader positioned at a gantry object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        GantryObj: The parsed gantry object.
    """
    reader.verify_id(TokenID.Gantry)

    gantry_obj = GantryObj()
    gantry_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            gantry_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            gantry_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            gantry_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            gantry_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            gantry_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            gantry_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            gantry_obj.static_flags = sub_block.read_flags()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return gantry_obj


def read_pickup_object(reader: BlockReader, detail_level: int) -> PickupObj:
    """
    Read and parse a pickup object from a BlockReader.

    Consumes the `Pickup` block and its child blocks, returning a PickupObj object.

    Args:
        reader (BlockReader): Reader positioned at a pickup object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        PickupObj: The parsed pickup object.
    """
    reader.verify_id(TokenID.Pickup)

    pickup_obj = PickupObj()
    pickup_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            pickup_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            pickup_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            pickup_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            pickup_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            pickup_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            pickup_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            pickup_obj.static_flags = sub_block.read_flags()

        elif sub_block.id == TokenID.SpeedRange:
            min_mps = sub_block.read_float()
            max_mps = sub_block.read_float()

            pickup_obj.speed_range = SpeedRange(
                min_mps=min_mps,
                max_mps=max_mps
            )

        elif sub_block.id == TokenID.PickupType:
            pickup_obj.pickup_type = sub_block.read_uint()
            pickup_obj.unknown = sub_block.read_uint()

        elif sub_block.id == TokenID.ORTSMaxStackedContainers:
            pickup_obj.max_stacked_containers = sub_block.read_int()

        elif sub_block.id == TokenID.ORTSStackLocationsLength:
            pickup_obj.stack_locations_length = sub_block.read_float()

        elif sub_block.id == TokenID.ORTSStackLocations:
            pickup_obj.stack_locations = read_stack_locations(sub_block)

        elif sub_block.id == TokenID.ORTSPickingSurfaceYOffset:
            pickup_obj.picking_surface_y_offset = sub_block.read_float()

        elif sub_block.id == TokenID.ORTSPickingSurfaceRelativeTopStartPosition:
            x = sub_block.read_float()
            y = sub_block.read_float()
            z = sub_block.read_float()

            pickup_obj.picking_surface_relative_top_start_position = Position(
                x=x,
                y=y,
                z=z
            )

        elif sub_block.id == TokenID.ORTSGrabberArmsParts:
            pickup_obj.grabber_arms_parts = sub_block.read_int()

        elif sub_block.id == TokenID.ORTSCraneSound:
            pickup_obj.crane_sound = sub_block.read_string()

        elif sub_block.id == TokenID.PickupAnimData:
            pickup_options = sub_block.read_float()
            animation_speed = sub_block.read_float()

            pickup_obj.pickup_anim_data = PickupAnimData(
                pickup_options=pickup_options,
                animation_speed=animation_speed
            )

        elif sub_block.id == TokenID.PickupCapacity:
            quantity_available_kg = sub_block.read_float() * (1.0 / 2.20462) # convert from lb to kg
            feed_rate_kg_per_s = sub_block.read_float() * (1.0 / 2.20462) # convert from lb to kg

            pickup_obj.pickup_capacity = PickupCapacity(
                quantity_available_kg=quantity_available_kg,
                feed_rate_kg_per_s=feed_rate_kg_per_s
            )
        
        elif sub_block.id == TokenID.TrItemId:
            if pickup_obj.tr_item_ids is None:
                pickup_obj.tr_item_ids = []
            
            tr_item_id = read_tr_item_id(sub_block)
            pickup_obj.tr_item_ids.append(tr_item_id)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return pickup_obj


def read_stack_locations(reader: BlockReader) -> List[StackLocation]:
    """
    Read and parse stack locations from a BlockReader.

    Consumes the `ORTSStackLocations` block and returns a list of StackLocation objects.

    Args:
        reader (BlockReader): Reader positioned at a stack locations block.

    Returns:
        List[StackLocation]: The parsed stack locations.
    """
    reader.verify_id(TokenID.ORTSStackLocations)

    stack_locations: List[StackLocation] = []
    count = reader.read_int()

    for sub_block in reader:
        if sub_block.id == TokenID.StackLocation:
            stack_location = StackLocation()

            for sub_sub_block in reader:
                if sub_sub_block.id == TokenID.Position:
                    stack_location.position = read_position(sub_sub_block)
                
                elif sub_sub_block.id == TokenID.MaxStackedContainers:
                    stack_location.max_stacked_containers = sub_sub_block.read_int()
                
                elif sub_sub_block.id == TokenID.Length:
                    stack_location.length = sub_sub_block.read_float()
                
                elif sub_sub_block.id == TokenID.Flipped:
                    sub_sub_block.read_int()
                    stack_location.flipped = True

                else:
                    logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
                    sub_block.skip()

            stack_locations.append(stack_location)

        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    reader.verify_count(count, len(stack_locations))

    return stack_locations


def read_hazard_object(reader: BlockReader, detail_level: int) -> HazardObj:
    """
    Read and parse a hazard object from a BlockReader.

    Consumes the `Hazard` block and its child blocks, returning a HazardObj object.

    Args:
        reader (BlockReader): Reader positioned at a hazard object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        HazardObj: The parsed hazard object.
    """
    reader.verify_id(TokenID.Hazard)

    hazard_obj = HazardObj()
    hazard_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            hazard_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            hazard_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            hazard_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            hazard_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            hazard_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            hazard_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            hazard_obj.static_flags = sub_block.read_flags()

        elif sub_block.id == TokenID.TrItemId:
            hazard_obj.tr_item_id = read_tr_item_id(sub_block)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return hazard_obj


def read_signal_object(reader: BlockReader, detail_level: int) -> SignalObj:
    """
    Read and parse a signal object from a BlockReader.

    Consumes the `Signal` block and its child blocks, returning a SignalObj object.

    Args:
        reader (BlockReader): Reader positioned at a signal object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        SignalObj: The parsed signal object.
    """
    reader.verify_id(TokenID.Signal)

    signal_obj = SignalObj()
    signal_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            signal_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            signal_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            signal_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            signal_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            signal_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            signal_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.SignalSubObj:
            signal_obj.signal_sub_obj = sub_block.read_flags()

        elif sub_block.id == TokenID.SignalUnits:
            signal_obj.signal_units = read_signal_units(sub_block)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return signal_obj


def read_signal_units(reader: BlockReader) -> List[SignalUnit]:
    """
    Read and parse signal units from a BlockReader.

    Consumes the `SignalUnits` block and returns a list of SignalUnit objects.

    Args:
        reader (BlockReader): Reader positioned at a signal units block.

    Returns:
        List[SignalUnit]: The parsed signal units.
    """
    reader.verify_id(TokenID.SignalUnits)

    signal_units: List[SignalUnit] = []
    count = reader.read_uint()

    for sub_block in reader:
        if sub_block.id == TokenID.SignalUnit:
            signal_unit = SignalUnit()

            signal_unit.sub_obj = sub_block.read_int()

            with sub_block.sub_block(TokenID.TrItemId) as tr_item_id_block:
                signal_unit.tr_item_id = read_tr_item_id(tr_item_id_block)

            signal_units.append(signal_unit)

        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    reader.verify_count(count, len(signal_units))

    return signal_units


def read_speedpost_object(reader: BlockReader, detail_level: int) -> SpeedPostObj:
    """
    Read and parse a speed post object from a BlockReader.

    Consumes the `Speedpost` block and its child blocks, returning a SpeedPostObj object.

    Args:
        reader (BlockReader): Reader positioned at a speed post object block.
        detail_level (int): Detail level associated with the object.

    Returns:
        SpeedPostObj: The parsed speed post object.
    """
    reader.verify_id(TokenID.Speedpost)

    speedpost_obj = SpeedPostObj()
    speedpost_obj.static_detail_level = detail_level

    for sub_block in reader:
        if sub_block.id == TokenID.UiD:
            speedpost_obj.uid = sub_block.read_uint()

        elif sub_block.id == TokenID.FileName:
            speedpost_obj.file_name = sub_block.read_string()

        elif sub_block.id == TokenID.Position:
            speedpost_obj.position = read_position(sub_block)

        elif sub_block.id == TokenID.QDirection:
            speedpost_obj.direction = read_qdirection(sub_block)

        elif sub_block.id == TokenID.Matrix3x3:
            speedpost_obj.matrix3x3 = read_matrix3x3(sub_block)

        elif sub_block.id == TokenID.VDbId:
            speedpost_obj.vdb_id = sub_block.read_uint()

        elif sub_block.id == TokenID.StaticFlags:
            speedpost_obj.static_flags = sub_block.read_flags()
            
        elif sub_block.id == TokenID.Speed_Digit_Tex:
            speedpost_obj.speed_digit_tex = sub_block.read_string()

        elif sub_block.id == TokenID.Speed_Sign_Shape:
            num_shapes = sub_block.read_int()
            shape_info: List[float] = []

            for _ in range(num_shapes):
                shape_info.append(sub_block.read_float())
                shape_info.append(sub_block.read_float())
                shape_info.append(sub_block.read_float())
                shape_info.append(sub_block.read_float())

            speedpost_obj.sign_shape = SpeedSignShape(
                num_shapes=num_shapes,
                shape_info=shape_info
            )

        elif sub_block.id == TokenID.Speed_Text_Size:
            size = sub_block.read_float()
            dx = sub_block.read_float()
            dy = sub_block.read_float()

            speedpost_obj.text_size = SpeedTextSize(
                size=size,
                dx=dx,
                dy=dy
            )

        elif sub_block.id == TokenID.TrItemId:
            if speedpost_obj.tr_item_ids is None:
                speedpost_obj.tr_item_ids = []
            
            tr_item_id = read_tr_item_id(sub_block)
            speedpost_obj.tr_item_ids.append(tr_item_id)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return speedpost_obj


def read_position(reader: BlockReader) -> Position:
    """
    Read and parse a position from a BlockReader.

    Consumes the `Position` block and returns a Position object.

    Args:
        reader (BlockReader): Reader positioned at a position block.

    Returns:
        Position: The parsed position.
    """
    reader.verify_id(TokenID.Position)

    x = reader.read_float()
    y = reader.read_float()
    z = reader.read_float()

    return Position(
        x=x,
        y=y,
        z=z
    )


def read_qdirection(reader: BlockReader) -> QDirection:
    """
    Read and parse a quaternion direction from a BlockReader.

    Consumes the `QDirection` block and returns a QDirection object.

    Args:
        reader (BlockReader): Reader positioned at a quaternion direction block.

    Returns:
        QDirection: The parsed quaternion direction.
    """
    reader.verify_id(TokenID.QDirection)

    x = reader.read_float()
    y = reader.read_float()
    z = reader.read_float()
    w = reader.read_float()

    return QDirection(
        x=x,
        y=y,
        z=z,
        w=w
    )


def read_matrix3x3(reader: BlockReader) -> Matrix3x3:
    """
    Read and parse a 3x3 matrix from a BlockReader.

    Consumes the `Matrix3x3` block and returns a Matrix3x3 object.

    Args:
        reader (BlockReader): Reader positioned at a 3x3 matrix block.

    Returns:
        Matrix3x3: The parsed 3x3 matrix.
    """
    reader.verify_id(TokenID.Matrix3x3)

    ax = reader.read_float()
    ay = reader.read_float()
    az = reader.read_float()
    bx = reader.read_float()
    by = reader.read_float()
    bz = reader.read_float()
    cx = reader.read_float()
    cy = reader.read_float()
    cz = reader.read_float()

    return Matrix3x3(
        ax=ax,
        ay=ay,
        az=az,
        bx=bx,
        by=by,
        bz=bz,
        cx=cx,
        cy=cy,
        cz=cz
    )


def read_jnode_position(reader: BlockReader) -> JNodePosition:
    """
    Read and parse a junction node position from a BlockReader.

    Consumes the `JNodePosn` block and returns a JNodePosition object.

    Args:
        reader (BlockReader): Reader positioned at a junction node position block.

    Returns:
        JNodePosition: The parsed junction node position.
    """
    reader.verify_id(TokenID.JNodePosn)

    tile_x = reader.read_int()
    tile_z = reader.read_int()
    x = reader.read_float()
    y = reader.read_float()
    z = reader.read_float()

    return JNodePosition(
        tile_x=tile_x,
        tile_z=tile_z,
        x=x,
        y=y,
        z=z
    )


def read_tr_item_id(reader: BlockReader) -> TrItemId:
    """
    Read and parse a track item ID from a BlockReader.

    Consumes the `TrItemId` block and returns a TrItemId object.

    Args:
        reader (BlockReader): Reader positioned at a track item ID block.

    Returns:
        TrItemId: The parsed track item ID.
    """
    reader.verify_id(TokenID.TrItemId)

    db = reader.read_int()
    db_id = reader.read_int()

    return TrItemId(
        db=db,
        db_id=db_id
    )