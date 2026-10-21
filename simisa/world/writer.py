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

from typing import List

from .. import TokenID
from ..format import BlockFormat
from ..writer import BlockWriter
from ..verbosity import Verbose
from ..tracksections.writer import write_local_tracksections
from .models import *


def dump(
    world: World,
    filepath: str,
    binary: bool = False,
    ascii: bool = False,
    compressed: bool = False,
    verbose: Verbose = None
) -> None:
    """
    Write a world object to disk.

    This function supports both compressed/uncompressed as well as binary/text data.
    It writes the world data to the file at the given path.

    Args:
        world (World): The world object to write.
        filepath (str): Path to the output file.
        binary (bool): Whether to write binary data. Defaults to False.
        ascii (bool): Whether to write ASCII data. Defaults to False. Always True when binary or compressed.
        compressed (bool): Whether to write compressed data. Defaults to False.
        verbose (Verbose, optional): Verbosity level for logging.

    Raises:
        TypeError: If any parameter has an unexpected type.
        OSError: If the file cannot be written.
    """
    check_params = (
        ("world", world, World),
        ("filepath", filepath, str),
        ("binary", binary, bool),
        ("ascii", ascii, bool),
        ("compressed", compressed, bool),
    )

    for name, value, typ in check_params:
        if isinstance(value, typ):
            continue

        raise TypeError(
            f"Parameter '{name}' must be {typ.__name__}, "
            f"but got {type(value).__name__}"
        )
    
    with BlockWriter.open(
        filepath,
        filetype="w",
        fileversion=0,
        is_binary=binary,
        is_utf16le=not ascii and not binary and not compressed,
        is_compressed=compressed,
        verbose=verbose
    ) as writer:
        write_world(writer, world)


def dumps(world: World, verbose: Verbose = None) -> str:
    """
    Write a world object to a string.

    This function does not support binary or compressed data. It writes world
    data to a string and returns it.

    Args:
        world (World): The world object to write.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        str: The string containing the world data.

    Raises:
        TypeError: If `world` is not a World object.
    """
    if not isinstance(world, World):
        raise TypeError(f"Parameter 'world' must be World, but got {type(world).__name__}")

    world_text = BlockWriter.to_string(
        lambda writer: write_world(writer, world),
        filetype="w",
        fileversion=0,
        verbose=verbose
    )

    return world_text


DEFAULT_LIST = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_count=True,
    newline_before_closing=True,
    newline_after_closing=True
)

WORLD_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_start=True,
    newline_before_closing=True
)

WORLD_OBJ_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_start=True,
    newline_before_closing=True
)

TRACKSECTIONS_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

SIGNAL_UNIT_BLOCK = BlockFormat(
    newline_before_closing=True
)

TR_ITEM_ID_BLOCK = BlockFormat(
    newline_before_block=True
)


def write_world(writer: BlockWriter, world: World) -> None:
    """
    Write a world block to a BlockWriter.

    Writes the `Tr_Worldfile` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the world block to.
        world (World): The world object to write.
    """
    with writer.sub_block(TokenID.Tr_Worldfile, block_format=WORLD_BLOCK) as worldfile_block:
        write_world_objects(worldfile_block, world.objects)


def write_world_objects(writer: BlockWriter, objects: List[WorldObj]) -> None:
    """
    Write world objects to a BlockWriter.

    Writes world objects by dispatching to the appropriate object type writer.

    Args:
        writer (BlockWriter): Writer to write the world objects to.
        objects (List[WorldObj]): List of world object objects to write.
    """
    for world_obj in objects:
        if not isinstance(world_obj, WorldObj):
            raise TypeError(f"World property 'objects' must contain WorldObj objects, but got {type(world_obj).__name__}")

    # User might have inserted an object without thinking about the ordering of objects by static_detail_level.
    # The order really matters here due to how static_detail_level gets stored in the world file.
    # So, sort the objects just in case, so that the watermark insertion always works properly.
    sorted_objects = sorted(objects, key=lambda obj: obj.static_detail_level)

    current_watermark = 0

    for world_obj in sorted_objects:
        if current_watermark != world_obj.static_detail_level:
            write_watermark(writer, world_obj.static_detail_level)
            current_watermark = world_obj.static_detail_level

        if isinstance(world_obj, StaticObj):
            write_static_object(writer, world_obj)
        
        elif isinstance(world_obj, TrackObj):
            write_track_object(writer, world_obj)
        
        elif isinstance(world_obj, CarSpawnerObj):
            write_carspawner_object(writer, world_obj)
        
        elif isinstance(world_obj, SidingObj):
            write_siding_object(writer, world_obj)
        
        elif isinstance(world_obj, PlatformObj):
            write_platform_object(writer, world_obj)
        
        elif isinstance(world_obj, ForestObj):
            write_forest_object(writer, world_obj)
        
        elif isinstance(world_obj, LevelCrObj):
            write_levelcr_object(writer, world_obj)
        
        elif isinstance(world_obj, DynTrackObj):
            write_dyntrack_object(writer, world_obj)
        
        elif isinstance(world_obj, TransferObj):
            write_transfer_object(writer, world_obj)
        
        elif isinstance(world_obj, GantryObj):
            write_gantry_object(writer, world_obj)
        
        elif isinstance(world_obj, PickupObj):
            write_pickup_object(writer, world_obj)
        
        elif isinstance(world_obj, HazardObj):
            write_hazard_object(writer, world_obj)
        
        elif isinstance(world_obj, SignalObj):
            write_signal_object(writer, world_obj)
        
        elif isinstance(world_obj, SpeedPostObj):
            write_speedpost_object(writer, world_obj)


def write_watermark(writer: BlockWriter, detail_level: int) -> None:
    """
    Write a watermark to a BlockWriter.

    Writes the `Tr_Watermark` sub-block with its detail level value.

    Args:
        writer (BlockWriter): Writer to write the static object to.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(detail_level, int):
        raise TypeError(f"Parameter 'detail_level' must be int, but got {type(detail_level).__name__}")

    with writer.sub_block(TokenID.Tr_Watermark) as watermark_block:
        watermark_block.write_int(detail_level)
    

def write_static_object(writer: BlockWriter, static_obj: StaticObj) -> None:
    """
    Write a static object to a BlockWriter.

    Writes the `Static` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the static object to.
        static_obj (StaticObj): The static object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(static_obj, StaticObj):
        raise TypeError(f"World property 'objects' must contain StaticObj objects, but got {type(static_obj).__name__}")

    with writer.sub_block(TokenID.Static, block_format=WORLD_OBJ_BLOCK) as static_block:
        with static_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(static_obj.uid)
    
        if static_obj.file_name is not None:
            with static_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(static_obj.file_name)
    
        with static_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(static_obj.static_flags)
    
        write_position(static_block, static_obj.position)
        write_qdirection(static_block, static_obj.direction)

        if static_obj.matrix3x3 is not None:
            write_matrix3x3(static_block, static_obj.matrix3x3)
    
        if static_obj.vdb_id is not None:
            with static_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(static_obj.vdb_id)


def write_track_object(writer: BlockWriter, track_obj: TrackObj) -> None:
    """
    Write a track object to a BlockWriter.

    Writes the `TrackObj` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the track object to.
        track_obj (TrackObj): The track object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(track_obj, TrackObj):
        raise TypeError(f"World property 'objects' must contain TrackObj objects, but got {type(track_obj).__name__}")

    with writer.sub_block(TokenID.TrackObj, block_format=WORLD_OBJ_BLOCK) as trackobj_block:
        with trackobj_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(track_obj.uid)

        with trackobj_block.sub_block(TokenID.SectionIdx) as sectionidx_block:
            sectionidx_block.write_uint(track_obj.section_index)
        
        with trackobj_block.sub_block(TokenID.Elevation) as elevation_block:
            elevation_block.write_float(track_obj.elevation)

        if track_obj.jnode_position is not None:
            write_jnode_position(trackobj_block, track_obj.jnode_position)
        
        with trackobj_block.sub_block(TokenID.CollideFlags) as collide_flags_block:
            collide_flags_block.write_flags(track_obj.collide_flags)
    
        if track_obj.file_name is not None:
            with trackobj_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(track_obj.file_name)
        
        with trackobj_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(track_obj.static_flags)
    
        write_position(trackobj_block, track_obj.position)
        write_qdirection(trackobj_block, track_obj.direction)

        if track_obj.matrix3x3 is not None:
            write_matrix3x3(trackobj_block, track_obj.matrix3x3)
    
        if track_obj.vdb_id is not None:
            with trackobj_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(track_obj.vdb_id)


def write_carspawner_object(writer: BlockWriter, car_spawner_obj: CarSpawnerObj) -> None:
    """
    Write a car spawner object to a BlockWriter.

    Writes the `CarSpawner` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the car spawner object to.
        car_spawner_obj (CarSpawnerObj): The car spawner object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(car_spawner_obj, CarSpawnerObj):
        raise TypeError(f"World property 'objects' must contain CarSpawnerObj objects, but got {type(car_spawner_obj).__name__}")

    with writer.sub_block(TokenID.CarSpawner, block_format=WORLD_OBJ_BLOCK) as car_spawner_block:
        with car_spawner_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(car_spawner_obj.uid)

        with car_spawner_block.sub_block(TokenID.CarFrequency) as car_frequency_block:
            car_frequency_block.write_float(car_spawner_obj.car_frequency)
        
        with car_spawner_block.sub_block(TokenID.CarAvSpeed) as car_av_speed_block:
            car_av_speed_block.write_float(car_spawner_obj.car_avg_speed)
        
        if car_spawner_obj.tr_item_ids:
            for tr_item_id in car_spawner_obj.tr_item_ids:
                write_tr_item_id(car_spawner_block, tr_item_id)
    
        if car_spawner_obj.file_name is not None:
            with car_spawner_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(car_spawner_obj.file_name)
    
        with car_spawner_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(car_spawner_obj.static_flags)
        
        if car_spawner_obj.list_name is not None:
            with car_spawner_block.sub_block(TokenID.ORTSListName) as listname_block:
                listname_block.write_string(car_spawner_obj.list_name)
    
        write_position(car_spawner_block, car_spawner_obj.position)
        write_qdirection(car_spawner_block, car_spawner_obj.direction)

        if car_spawner_obj.matrix3x3 is not None:
            write_matrix3x3(car_spawner_block, car_spawner_obj.matrix3x3)
    
        if car_spawner_obj.vdb_id is not None:
            with car_spawner_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(car_spawner_obj.vdb_id)


def write_siding_object(writer: BlockWriter, siding_obj: SidingObj) -> None:
    """
    Write a siding object to a BlockWriter.

    Writes the `Siding` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the siding object to.
        siding_obj (SidingObj): The siding object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(siding_obj, SidingObj):
        raise TypeError(f"World property 'objects' must contain SidingObj objects, but got {type(siding_obj).__name__}")

    with writer.sub_block(TokenID.Siding, block_format=WORLD_OBJ_BLOCK) as siding_block:
        with siding_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(siding_obj.uid)
    
        with siding_block.sub_block(TokenID.SidingData) as siding_data_block:
            siding_data_block.write_flags(siding_obj.siding_data)

        if siding_obj.tr_item_ids:
            for tr_item_id in siding_obj.tr_item_ids:
                write_tr_item_id(siding_block, tr_item_id)
        
        if siding_obj.file_name is not None:
            with siding_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(siding_obj.file_name)
    
        with siding_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(siding_obj.static_flags)
    
        write_position(siding_block, siding_obj.position)
        write_qdirection(siding_block, siding_obj.direction)

        if siding_obj.matrix3x3 is not None:
            write_matrix3x3(siding_block, siding_obj.matrix3x3)
    
        if siding_obj.vdb_id is not None:
            with siding_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(siding_obj.vdb_id)


def write_platform_object(writer: BlockWriter, platform_obj: PlatformObj) -> None:
    """
    Write a platform object to a BlockWriter.

    Writes the `Platform` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the platform object to.
        platform_obj (PlatformObj): The platform object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(platform_obj, PlatformObj):
        raise TypeError(f"World property 'objects' must contain PlatformObj objects, but got {type(platform_obj).__name__}")

    with writer.sub_block(TokenID.Platform, block_format=WORLD_OBJ_BLOCK) as platform_block:
        with platform_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(platform_obj.uid)

        with platform_block.sub_block(TokenID.PlatformData) as platform_data_block:
            platform_data_block.write_flags(platform_obj.platform_data)
        
        if platform_obj.tr_item_ids:
            for tr_item_id in platform_obj.tr_item_ids:
                write_tr_item_id(platform_block, tr_item_id)
    
        if platform_obj.file_name is not None:
            with platform_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(platform_obj.file_name)
    
        with platform_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(platform_obj.static_flags)
    
        write_position(platform_block, platform_obj.position)
        write_qdirection(platform_block, platform_obj.direction)

        if platform_obj.matrix3x3 is not None:
            write_matrix3x3(platform_block, platform_obj.matrix3x3)
    
        if platform_obj.vdb_id is not None:
            with platform_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(platform_obj.vdb_id)


def write_forest_object(writer: BlockWriter, forest_obj: ForestObj) -> None:
    """
    Write a forest object to a BlockWriter.

    Writes the `Forest` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the forest object to.
        forest_obj (ForestObj): The forest object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(forest_obj, ForestObj):
        raise TypeError(f"World property 'objects' must contain ForestObj objects, but got {type(forest_obj).__name__}")

    with writer.sub_block(TokenID.Forest, block_format=WORLD_OBJ_BLOCK) as forest_block:
        with forest_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(forest_obj.uid)

        if forest_obj.tree_texture is not None:
            with forest_block.sub_block(TokenID.TreeTexture) as tree_texture_block:
                tree_texture_block.write_string(forest_obj.tree_texture)
        
        if forest_obj.scale_range is not None:
            with forest_block.sub_block(TokenID.ScaleRange) as scale_range_block:
                scale_range_block.write_float(forest_obj.scale_range.minimum)
                scale_range_block.write_float(forest_obj.scale_range.maximum)
        
        if forest_obj.forest_area is not None:
            with forest_block.sub_block(TokenID.Area) as area_block:
                area_block.write_float(forest_obj.forest_area.x)
                area_block.write_float(forest_obj.forest_area.z)
        
        if forest_obj.population is not None:
            with forest_block.sub_block(TokenID.Population) as population_block:
                population_block.write_int(forest_obj.population)
        
        if forest_obj.tree_size is not None:
            with forest_block.sub_block(TokenID.TreeSize) as tree_size_block:
                tree_size_block.write_float(forest_obj.tree_size.width)
                tree_size_block.write_float(forest_obj.tree_size.height)
    
        if forest_obj.file_name is not None:
            with forest_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(forest_obj.file_name)
    
        with forest_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(forest_obj.static_flags)
    
        write_position(forest_block, forest_obj.position)
        write_qdirection(forest_block, forest_obj.direction)

        if forest_obj.matrix3x3 is not None:
            write_matrix3x3(forest_block, forest_obj.matrix3x3)
    
        if forest_obj.vdb_id is not None:
            with forest_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(forest_obj.vdb_id)


def write_levelcr_object(writer: BlockWriter, levelcr_obj: LevelCrObj) -> None:
    """
    Write a level crossing object to a BlockWriter.

    Writes the `LevelCr` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the level crossing object to.
        levelcr_obj (LevelCrObj): The level crossing object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(levelcr_obj, LevelCrObj):
        raise TypeError(f"World property 'objects' must contain LevelCrObj objects, but got {type(levelcr_obj).__name__}")

    with writer.sub_block(TokenID.LevelCr, block_format=WORLD_OBJ_BLOCK) as levelcr_block:
        with levelcr_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(levelcr_obj.uid)
        
        if levelcr_obj.levelcr_params is not None:
            with levelcr_block.sub_block(TokenID.LevelCrParameters) as levelcr_params_block:
                levelcr_params_block.write_float(levelcr_obj.levelcr_params.warning_time)
                levelcr_params_block.write_float(levelcr_obj.levelcr_params.minimum_distance)
        
        if levelcr_obj.crash_probability is not None:
            with levelcr_block.sub_block(TokenID.CrashProbability) as crash_probability_block:
                crash_probability_block.write_int(levelcr_obj.crash_probability)
        
        if levelcr_obj.levelcr_data is not None:
            with levelcr_block.sub_block(TokenID.LevelCrData) as levelcr_data_block:
                levelcr_data_block.write_flags(levelcr_obj.levelcr_data.data1)
                levelcr_data_block.write_flags(levelcr_obj.levelcr_data.data2)
        
        if levelcr_obj.levelcr_timing is not None:
            with levelcr_block.sub_block(TokenID.LevelCrTiming) as levelcr_timing_block:
                levelcr_timing_block.write_float(levelcr_obj.levelcr_timing.initial_timing)
                levelcr_timing_block.write_float(levelcr_obj.levelcr_timing.serious_timing)
                levelcr_timing_block.write_float(levelcr_obj.levelcr_timing.animation_timing)
        
        if levelcr_obj.sound_filename:
            with levelcr_block.sub_block(TokenID.ORTSSoundFileName) as sound_filename_block:
                sound_filename_block.write_string(levelcr_obj.sound_filename)
        
        if levelcr_obj.tr_item_ids:
            for tr_item_id in levelcr_obj.tr_item_ids:
                write_tr_item_id(levelcr_block, tr_item_id)
    
        if levelcr_obj.file_name is not None:
            with levelcr_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(levelcr_obj.file_name)
    
        with levelcr_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(levelcr_obj.static_flags)
    
        write_position(levelcr_block, levelcr_obj.position)
        write_qdirection(levelcr_block, levelcr_obj.direction)

        if levelcr_obj.matrix3x3 is not None:
            write_matrix3x3(levelcr_block, levelcr_obj.matrix3x3)
    
        if levelcr_obj.vdb_id is not None:
            with levelcr_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(levelcr_obj.vdb_id)



def write_dyntrack_object(writer: BlockWriter, dyntrack_obj: DynTrackObj) -> None:
    """
    Write a dynamic track object to a BlockWriter.

    Writes the `Dyntrack` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the dynamic track object to.
        dyntrack_obj (DynTrackObj): The dynamic track object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(dyntrack_obj, DynTrackObj):
        raise TypeError(f"World property 'objects' must contain DynTrackObj objects, but got {type(dyntrack_obj).__name__}")

    with writer.sub_block(TokenID.Dyntrack, block_format=WORLD_OBJ_BLOCK) as dyntrack_block:
        with dyntrack_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(dyntrack_obj.uid)

        if dyntrack_obj.track_sections is not None:
            with dyntrack_block.sub_block(TokenID.TrackSections, block_format=TRACKSECTIONS_BLOCK) as tracksections_block:
                write_local_tracksections(tracksections_block, dyntrack_obj.track_sections, write_max_sections=False)
        
        with dyntrack_block.sub_block(TokenID.SectionIdx) as sectionidx_block:
            sectionidx_block.write_uint(dyntrack_obj.section_index)
        
        with dyntrack_block.sub_block(TokenID.Elevation) as elevation_block:
            elevation_block.write_float(dyntrack_obj.elevation)
        
        with dyntrack_block.sub_block(TokenID.CollideFlags) as collide_flags_block:
            collide_flags_block.write_uint(dyntrack_obj.collide_flags)
        
        with dyntrack_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(dyntrack_obj.static_flags)

        write_position(dyntrack_block, dyntrack_obj.position)
        write_qdirection(dyntrack_block, dyntrack_obj.direction)

        if dyntrack_obj.vdb_id is not None:
            with dyntrack_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(dyntrack_obj.vdb_id)


def write_transfer_object(writer: BlockWriter, transfer_obj: TransferObj) -> None:
    """
    Write a transfer object to a BlockWriter.

    Writes the `Transfer` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the transfer object to.
        transfer_obj (TransferObj): The transfer object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(transfer_obj, TransferObj):
        raise TypeError(f"World property 'objects' must contain TransferObj objects, but got {type(transfer_obj).__name__}")

    with writer.sub_block(TokenID.Transfer, block_format=WORLD_OBJ_BLOCK) as transfer_block:
        with transfer_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(transfer_obj.uid)

        with transfer_block.sub_block(TokenID.Width) as width_block:
            width_block.write_float(transfer_obj.width)
        
        with transfer_block.sub_block(TokenID.Height) as height_block:
            height_block.write_float(transfer_obj.height)
    
        if transfer_obj.file_name is not None:
            with transfer_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(transfer_obj.file_name)
    
        with transfer_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(transfer_obj.static_flags)
    
        write_position(transfer_block, transfer_obj.position)
        write_qdirection(transfer_block, transfer_obj.direction)

        if transfer_obj.matrix3x3 is not None:
            write_matrix3x3(transfer_block, transfer_obj.matrix3x3)
    
        if transfer_obj.vdb_id is not None:
            with transfer_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(transfer_obj.vdb_id)


def write_gantry_object(writer: BlockWriter, gantry_obj: GantryObj) -> None:
    """
    Write a gantry object to a BlockWriter.

    Writes the `Gantry` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the gantry object to.
        gantry_obj (GantryObj): The gantry object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(gantry_obj, GantryObj):
        raise TypeError(f"World property 'objects' must contain GantryObj objects, but got {type(gantry_obj).__name__}")

    with writer.sub_block(TokenID.Gantry, block_format=WORLD_OBJ_BLOCK) as gantry_block:
        with gantry_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(gantry_obj.uid)
    
        if gantry_obj.file_name is not None:
            with gantry_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(gantry_obj.file_name)
    
        with gantry_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(gantry_obj.static_flags)
    
        write_position(gantry_block, gantry_obj.position)
        write_qdirection(gantry_block, gantry_obj.direction)

        if gantry_obj.matrix3x3 is not None:
            write_matrix3x3(gantry_block, gantry_obj.matrix3x3)
    
        if gantry_obj.vdb_id is not None:
            with gantry_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(gantry_obj.vdb_id)
    
        with gantry_block.sub_block(TokenID.StaticDetailLevel) as static_detail_level_block:
            static_detail_level_block.write_uint(gantry_obj.static_detail_level)


def write_pickup_object(writer: BlockWriter, pickup_obj: PickupObj) -> None:
    """
    Write a pickup object to a BlockWriter.

    Writes the `Pickup` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the pickup object to.
        pickup_obj (PickupObj): The pickup object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(pickup_obj, PickupObj):
        raise TypeError(f"World property 'objects' must contain PickupObj objects, but got {type(pickup_obj).__name__}")

    with writer.sub_block(TokenID.Pickup, block_format=WORLD_OBJ_BLOCK) as pickup_block:
        with pickup_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(pickup_obj.uid)

        if pickup_obj.speed_range is not None:
            with pickup_block.sub_block(TokenID.SpeedRange) as speed_range_block:
                speed_range_block.write_float(pickup_obj.speed_range.min_mps)
                speed_range_block.write_float(pickup_obj.speed_range.max_mps)
        
        with pickup_block.sub_block(TokenID.PickupType) as pickup_type_block:
            pickup_type_block.write_uint(pickup_obj.pickup_type)
            pickup_type_block.write_uint(pickup_obj.unknown)
        
        if pickup_obj.max_stacked_containers is not None:
            with pickup_block.sub_block(TokenID.ORTSMaxStackedContainers) as max_stacked_containers_block:
                max_stacked_containers_block.write_int(pickup_obj.max_stacked_containers)
        
        if pickup_obj.stack_locations_length is not None:
            with pickup_block.sub_block(TokenID.ORTSStackLocationsLength) as stack_locations_length_block:
                stack_locations_length_block.write_float(pickup_obj.stack_locations_length)
        
        if pickup_obj.stack_locations:
            write_stack_locations(pickup_block, pickup_obj.stack_locations)
        
        with pickup_block.sub_block(TokenID.ORTSPickingSurfaceYOffset) as picking_surface_y_offset_block:
            picking_surface_y_offset_block.write_float(pickup_obj.picking_surface_y_offset)
        
        if pickup_obj.picking_surface_relative_top_start_position is not None:
            with pickup_block.sub_block(TokenID.ORTSPickingSurfaceRelativeTopStartPosition) as top_start_position_block:
                top_start_position_block.write_float(pickup_obj.picking_surface_relative_top_start_position.x)
                top_start_position_block.write_float(pickup_obj.picking_surface_relative_top_start_position.y)
                top_start_position_block.write_float(pickup_obj.picking_surface_relative_top_start_position.z)
        
        with pickup_block.sub_block(TokenID.ORTSGrabberArmsParts) as grabber_arms_parts_block:
            grabber_arms_parts_block.write_int(pickup_obj.grabber_arms_parts)
        
        if pickup_obj.crane_sound is not None:
            with pickup_block.sub_block(TokenID.ORTSCraneSound) as crane_sound_block:
                crane_sound_block.write_string(pickup_obj.crane_sound)
        
        if pickup_obj.pickup_anim_data is not None:
            with pickup_block.sub_block(TokenID.PickupAnimData) as pickup_anim_data_block:
                pickup_anim_data_block.write_float(pickup_obj.pickup_anim_data.pickup_options)
                pickup_anim_data_block.write_float(pickup_obj.pickup_anim_data.animation_speed)
        
        if pickup_obj.pickup_capacity is not None:
            with pickup_block.sub_block(TokenID.PickupCapacity) as pickup_capacity_block:
                pickup_capacity_block.write_float(pickup_obj.pickup_capacity.quantity_available_kg * 2.20462) # convert from kg to lb
                pickup_capacity_block.write_float(pickup_obj.pickup_capacity.feed_rate_kg_per_s * 2.20462) # convert from kg to lb
        
        if pickup_obj.tr_item_ids:
            for tr_item_id in pickup_obj.tr_item_ids:
                write_tr_item_id(pickup_block, tr_item_id)
    
        if pickup_obj.file_name is not None:
            with pickup_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(pickup_obj.file_name)
    
        with pickup_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(pickup_obj.static_flags)
    
        write_position(pickup_block, pickup_obj.position)
        write_qdirection(pickup_block, pickup_obj.direction)

        if pickup_obj.matrix3x3 is not None:
            write_matrix3x3(pickup_block, pickup_obj.matrix3x3)
    
        if pickup_obj.vdb_id is not None:
            with pickup_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(pickup_obj.vdb_id)


def write_stack_locations(writer: BlockWriter, stack_locations: List[StackLocation]) -> None:
    """
    Write stack locations to a BlockWriter.

    Writes the `ORTSStackLocations` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the stack locations block to.
        stack_locations (List[StackLocation]): List of stack location objects to write.
    """
    for stack_location in stack_locations:
        if not isinstance(stack_location, StackLocation):
            raise TypeError(f"TransferObj property 'stack_locations' must contain StackLocation objects, but got {type(stack_location).__name__}")

    with writer.sub_block(TokenID.ORTSStackLocations) as stack_locations_block:
        stack_locations_block.write_count(len(stack_locations))

        for stack_location in stack_locations:
            with stack_locations_block.sub_block(TokenID.StackLocation) as stack_location_block:
                if stack_location.position is not None:
                    write_position(stack_location_block, stack_location.position)
                
                with stack_location_block.sub_block(TokenID.MaxStackedContainers) as max_stacked_containers_block:
                    max_stacked_containers_block.write_int(stack_location.max_stacked_containers)
                
                with stack_location_block.sub_block(TokenID.Length) as length_block:
                    length_block.write_float(stack_location.length)
                
                if stack_location.flipped:
                    with stack_location_block.sub_block(TokenID.Flipped) as flipped_block:
                        flipped_block.write_int(1)


def write_hazard_object(writer: BlockWriter, hazard_obj: HazardObj) -> None:
    """
    Write a hazard object to a BlockWriter.

    Writes the `Hazard` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the hazard object to.
        hazard_obj (HazardObj): The hazard object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(hazard_obj, HazardObj):
        raise TypeError(f"World property 'objects' must contain HazardObj objects, but got {type(hazard_obj).__name__}")

    with writer.sub_block(TokenID.Hazard, block_format=WORLD_OBJ_BLOCK) as hazard_block:
        with hazard_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(hazard_obj.uid)

        if hazard_obj.tr_item_id is not None:
            write_tr_item_id(hazard_block, hazard_obj.tr_item_id)
    
        if hazard_obj.file_name is not None:
            with hazard_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(hazard_obj.file_name)
    
        with hazard_block.sub_block(TokenID.StaticFlags) as static_flags_block:
            static_flags_block.write_flags(hazard_obj.static_flags)
    
        write_position(hazard_block, hazard_obj.position)
        write_qdirection(hazard_block, hazard_obj.direction)

        if hazard_obj.matrix3x3 is not None:
            write_matrix3x3(hazard_block, hazard_obj.matrix3x3)
    
        if hazard_obj.vdb_id is not None:
            with hazard_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(hazard_obj.vdb_id)


def write_signal_object(writer: BlockWriter, signal_obj: SignalObj) -> None:
    """
    Write a signal object to a BlockWriter.

    Writes the `Signal` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the signal object to.
        signal_obj (SignalObj): The signal object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(signal_obj, SignalObj):
        raise TypeError(f"World property 'objects' must contain SignalObj objects, but got {type(signal_obj).__name__}")

    with writer.sub_block(TokenID.Signal, block_format=WORLD_OBJ_BLOCK) as signal_block:
        with signal_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(signal_obj.uid)
    
        if signal_obj.file_name is not None:
            with signal_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(signal_obj.file_name)
    
        write_position(signal_block, signal_obj.position)
        write_qdirection(signal_block, signal_obj.direction)

        if signal_obj.matrix3x3 is not None:
            write_matrix3x3(signal_block, signal_obj.matrix3x3)
    
        if signal_obj.vdb_id is not None:
            with signal_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(signal_obj.vdb_id)

        with signal_block.sub_block(TokenID.SignalSubObj) as signal_sub_obj_block:
            signal_sub_obj_block.write_flags(signal_obj.signal_sub_obj)
        
        if signal_obj.signal_units:
            write_signal_units(signal_block, signal_obj.signal_units)


def write_signal_units(writer: BlockWriter, signal_units: List[SignalUnit]) -> None:
    """
    Write signal units to a BlockWriter.

    Writes the `SignalUnits` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the signal units block to.
        signal_units (List[SignalUnit]): List of signal unit objects to write.
    """
    for signal_unit in signal_units:
        if not isinstance(signal_unit, SignalUnit):
            raise TypeError(f"SignalObj property 'signal_units' must contain SignalUnit objects, but got {type(signal_unit).__name__}")

    with writer.sub_block(TokenID.SignalUnits, block_format=DEFAULT_LIST) as signal_units_block:
        signal_units_block.write_count(len(signal_units))

        for signal_unit in signal_units:
            with signal_units_block.sub_block(TokenID.SignalUnit, block_format=SIGNAL_UNIT_BLOCK) as signal_unit_block:
                signal_unit_block.write_int(signal_unit.sub_obj)
                write_tr_item_id(signal_unit_block, signal_unit.tr_item_id)


def write_speedpost_object(writer: BlockWriter, speedpost_obj: SpeedPostObj) -> None:
    """
    Write a speed post object to a BlockWriter.

    Writes the `Speedpost` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the speed post object to.
        speedpost_obj (SpeedPostObj): The speed post object to write.
        detail_level (int): Detail level associated with the object.
    """
    if not isinstance(speedpost_obj, SpeedPostObj):
        raise TypeError(f"World property 'objects' must contain SpeedPostObj objects, but got {type(speedpost_obj).__name__}")

    with writer.sub_block(TokenID.Speedpost, block_format=WORLD_OBJ_BLOCK) as speedpost_block:
        with speedpost_block.sub_block(TokenID.UiD) as uid_block:
            uid_block.write_uint(speedpost_obj.uid)

        if speedpost_obj.speed_digit_tex is not None:
            with speedpost_block.sub_block(TokenID.Speed_Digit_Tex) as speed_digit_tex_block:
                speed_digit_tex_block.write_string(speedpost_obj.speed_digit_tex)
        
        if speedpost_obj.sign_shape is not None:
            with speedpost_block.sub_block(TokenID.Speed_Sign_Shape) as sign_shape_block:
                sign_shape_block.write_int(speedpost_obj.sign_shape.num_shapes)

                for value in speedpost_obj.sign_shape.shape_info:
                    sign_shape_block.write_float(value)
        
        if speedpost_obj.text_size is not None:
            with speedpost_block.sub_block(TokenID.Speed_Text_Size) as text_size_block:
                text_size_block.write_float(speedpost_obj.text_size.size)
                text_size_block.write_float(speedpost_obj.text_size.dx)
                text_size_block.write_float(speedpost_obj.text_size.dy)
        
        if speedpost_obj.tr_item_ids:
            for tr_item_id in speedpost_obj.tr_item_ids:
                write_tr_item_id(speedpost_block, tr_item_id)
    
        if speedpost_obj.file_name is not None:
            with speedpost_block.sub_block(TokenID.FileName) as filename_block:
                filename_block.write_string(speedpost_obj.file_name)
    
        write_position(speedpost_block, speedpost_obj.position)
        write_qdirection(speedpost_block, speedpost_obj.direction)

        if speedpost_obj.matrix3x3 is not None:
            write_matrix3x3(speedpost_block, speedpost_obj.matrix3x3)
    
        if speedpost_obj.vdb_id is not None:
            with speedpost_block.sub_block(TokenID.VDbId) as vdb_id_block:
                vdb_id_block.write_uint(speedpost_obj.vdb_id)


def write_position(writer: BlockWriter, position: Position) -> None:
    """
    Write a position to a BlockWriter.

    Writes the `Position` sub-block.

    Args:
        writer (BlockWriter): Writer to write the position block to.
        position (Position): The position object to write.
    """
    if not isinstance(position, Position):
        raise TypeError(f"WorldObj property 'position' must be Position, but got {type(position).__name__}")

    with writer.sub_block(TokenID.Position) as position_block:
        position_block.write_float(position.x)
        position_block.write_float(position.y)
        position_block.write_float(position.z)


def write_qdirection(writer: BlockWriter, qdirection: QDirection) -> None:
    """
    Write a quaternion direction to a BlockWriter.

    Writes the `QDirection` sub-block.

    Args:
        writer (BlockWriter): Writer to write the quaternion direction block to.
        qdirection (QDirection): The quaternion direction object to write.
    """
    if not isinstance(qdirection, QDirection):
        raise TypeError(f"WorldObj property 'direction' must be QDirection, but got {type(qdirection).__name__}")

    with writer.sub_block(TokenID.QDirection) as qdirection_block:
        qdirection_block.write_float(qdirection.x)
        qdirection_block.write_float(qdirection.y)
        qdirection_block.write_float(qdirection.z)
        qdirection_block.write_float(qdirection.w)


def write_matrix3x3(writer: BlockWriter, matrix3x3: Matrix3x3) -> None:
    """
    Write a 3x3 matrix to a BlockWriter.

    Writes the `Matrix3x3` sub-block.

    Args:
        writer (BlockWriter): Writer to write the 3x3 matrix block to.
        matrix3x3 (Matrix3x3): The 3x3 matrix object to write.
    """
    if not isinstance(matrix3x3, Matrix3x3):
        raise TypeError(f"WorldObj property 'matrix3x3' must be Matrix3x3, but got {type(matrix3x3).__name__}")

    with writer.sub_block(TokenID.Matrix3x3) as matrix3x3_block:
        matrix3x3_block.write_float(matrix3x3.ax)
        matrix3x3_block.write_float(matrix3x3.ay)
        matrix3x3_block.write_float(matrix3x3.az)
        matrix3x3_block.write_float(matrix3x3.bx)
        matrix3x3_block.write_float(matrix3x3.by)
        matrix3x3_block.write_float(matrix3x3.bz)
        matrix3x3_block.write_float(matrix3x3.cx)
        matrix3x3_block.write_float(matrix3x3.cy)
        matrix3x3_block.write_float(matrix3x3.cz)


def write_jnode_position(writer: BlockWriter, jnode_position: JNodePosition) -> None:
    """
    Write a junction node position to a BlockWriter.

    Writes the `JNodePosn` sub-block.

    Args:
        writer (BlockWriter): Writer to write the junction node position block to.
        jnode_position (JNodePosition): The junction node position object to write.
    """
    if not isinstance(jnode_position, JNodePosition):
        raise TypeError(f"TrackObj property 'jnode_position' must be JNodePosition, but got {type(jnode_position).__name__}")

    with writer.sub_block(TokenID.JNodePosn) as jnode_position_block:
        jnode_position_block.write_int(jnode_position.tile_x)
        jnode_position_block.write_int(jnode_position.tile_z)
        jnode_position_block.write_float(jnode_position.x)
        jnode_position_block.write_float(jnode_position.y)
        jnode_position_block.write_float(jnode_position.z)


def write_tr_item_id(writer: BlockWriter, tr_item_id: TrItemId) -> None:
    """
    Write a track item ID to a BlockWriter.

    Writes the `TrItemId` sub-block.

    Args:
        writer (BlockWriter): Writer to write the track item ID block to.
        tr_item_id (TrItemId): The track item ID object to write.
    """
    if not isinstance(tr_item_id, TrItemId):
        raise TypeError(f"SignalUnit property 'tr_item_id' must be TrItemId, but got {type(tr_item_id).__name__}")

    with writer.sub_block(TokenID.TrItemId, block_format=TR_ITEM_ID_BLOCK) as tr_item_id_block:
        tr_item_id_block.write_int(tr_item_id.db)
        tr_item_id_block.write_int(tr_item_id.db_id)