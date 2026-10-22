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
) -> TrackDB:
    """
    Load and parse a track database file from disk.

    This function opens the file at the given path, validates that it is a supported tdb
    file based on its subheader, and returns a parsed `TrackDB` object.

    Args:
        filepath (str): Path to the tdb file.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        TrackDB: The parsed track database object.

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

        if not reader.filetype == 'T':
            raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a track database?")

        return read_trackdb(reader)


def loads(
    tdb_text: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> TrackDB:
    """
    Parse a track database from a string containing tdb data.

    This function does not support binary or compressed data. It reads tdb
    data from the provided string, validates that it represents a supported
    track database file based on its subheader, and returns a parsed `TrackDB` object.

    Args:
        tdb_text (str): String containing tdb file data.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        TrackDB: The parsed track database object.

    Raises:
        TypeError: If a parameter is not of the expected type.
        SimisaHeaderError: If the data has an invalid or unrecognized SIMISA header.
        SimisaSubheaderError: If the data has an invalid or unrecognized SIMISA subheader.
        BlockReaderError: If the block reader encounters an error or malformed data.
        StfReaderError: If the STF reader encounters an error or malformed data.
        UnresolvableIncludeError: If includes within the file cannot be resolved.
    """
    if not isinstance(tdb_text, str):
        raise TypeError(f"Parameter 'tdb_text' must be str, but got {type(tdb_text).__name__}")

    reader = BlockReader.from_string(tdb_text, progress=progress, verbose=verbose)

    if not reader.filetype == 'T':
        raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a track database?")

    return read_trackdb(reader)


def read_trackdb(reader: BlockReader) -> TrackDB:
    """
    Read and parse a track database from a BlockReader.

    Consumes the `TrackDB` block and its child blocks, returning a TrackDB object.

    Args:
        reader (BlockReader): Reader positioned at the start of a track database file.

    Returns:
        TrackDB: The parsed track database.
    """
    with reader.sub_block(TokenID.TrackDB) as trackdb_block:
        serial = 0

        with trackdb_block.sub_block(TokenID.Serial) as serial_block:
            serial = serial_block.read_uint()

        track_nodes = read_track_nodes(trackdb_block)
        tr_item_table = read_tr_item_table(trackdb_block)

        return TrackDB(
            serial=serial,
            track_nodes=track_nodes,
            tr_item_table=tr_item_table
        )


def read_track_nodes(reader: BlockReader) -> List[TrackNode]:
    """
    Read and parse track nodes from a BlockReader.

    Consumes the `TrackNodes` block and returns a list of TrackNode objects.

    Args:
        reader (BlockReader): Reader positioned at a track nodes block.

    Returns:
        List[TrackNode]: The parsed track nodes.
    """
    with reader.sub_block(TokenID.TrackNodes) as track_nodes_block:
        if track_nodes_block is None:
            return []
        
        track_nodes: List[TrackNode] = []
        count = track_nodes_block.read_uint()
        
        for track_node_block in track_nodes_block:
            track_node_block.verify_id(TokenID.TrackNode)

            index = track_node_block.read_uint()
            uid = None
            tr_junction_node = None
            tr_vector_node = None
            tr_end_node = False
            tr_pins = []
            inpins = 0
            outpins = 0

            for sub_block in track_node_block:
                if sub_block.id == TokenID.UiD:
                    uid = read_uid(sub_block)

                elif sub_block.id == TokenID.TrJunctionNode:
                    tr_junction_node = read_tr_junction_node(sub_block)

                elif sub_block.id == TokenID.TrVectorNode:
                    tr_vector_node = read_tr_vector_node(sub_block)

                elif sub_block.id == TokenID.TrEndNode:
                    tr_end_node = True
                    sub_block.skip()

                elif sub_block.id == TokenID.TrPins:
                    inpins = sub_block.read_uint()
                    outpins = sub_block.read_uint()

                    tr_pins = read_tr_pins(sub_block)

                    sub_block.verify_count(inpins + outpins, len(tr_pins))
                    sub_block.skip()
                
                else:
                    logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
                    sub_block.skip()

            track_node = TrackNode(
                index=index,
                uid=uid,
                tr_junction_node=tr_junction_node,
                tr_vector_node=tr_vector_node,
                tr_end_node=tr_end_node,
                tr_pins=tr_pins
            )
            track_nodes.append(track_node)

        track_nodes_block.verify_count(count, len(track_nodes))

        return track_nodes


def read_uid(reader: BlockReader) -> UiD:
    """
    Read and parse a UiD block from a BlockReader.

    Consumes the `UiD` block and returns a UiD object.

    Args:
        reader (BlockReader): Reader positioned at a UiD block.

    Returns:
        UiD: The parsed UiD.
    """
    reader.verify_id(TokenID.UiD)
    
    world_tile_x = reader.read_int()
    world_tile_z = reader.read_int()
    world_id = reader.read_int()
    _ = reader.read_int()
    tile_x = reader.read_int()
    tile_z = reader.read_int()
    x = reader.read_float()
    y = reader.read_float()
    z = reader.read_float()
    ax = reader.read_float()
    ay = reader.read_float()
    az = reader.read_float()

    reader.skip()

    return UiD(
        tile_x=tile_x,
        tile_z=tile_z,
        x=x,
        y=y,
        z=z,
        ax=ax,
        ay=ay,
        az=az,
        world_tile_x=world_tile_x,
        world_tile_z=world_tile_z,
        world_id=world_id
    )


def read_tr_junction_node(reader: BlockReader) -> TrJunctionNode:
    """
    Read and parse a track junction node from a BlockReader.

    Consumes the `TrJunctionNode` block and returns a TrJunctionNode object.

    Args:
        reader (BlockReader): Reader positioned at a track junction node block.

    Returns:
        TrJunctionNode: The parsed track junction node.
    """
    reader.verify_id(TokenID.TrJunctionNode)

    _ = reader.read_string()
    shape_index = reader.read_uint()

    reader.skip()

    return TrJunctionNode(
        shape_index=shape_index
    )


def read_tr_vector_node(reader: BlockReader) -> TrVectorNode:
    """
    Read and parse a track vector node from a BlockReader.

    Consumes the `TrVectorNode` block and its child blocks, returning a TrVectorNode object.

    Args:
        reader (BlockReader): Reader positioned at a track vector node block.

    Returns:
        TrVectorNode: The parsed track vector node.
    """
    reader.verify_id(TokenID.TrVectorNode)

    tr_vector_sections: List[TrVectorSection] = []
    tr_item_refs: List[int] = []

    for sub_block in reader:
        if sub_block.id == TokenID.TrVectorSections:
            tr_vector_sections = read_tr_vector_sections(sub_block)

        elif sub_block.id == TokenID.TrItemRefs:
            tr_item_refs = read_tr_item_refs(sub_block)

        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    reader.skip()

    return TrVectorNode(
        tr_vector_sections=tr_vector_sections,
        tr_item_refs=tr_item_refs
    )


def read_tr_vector_sections(reader: BlockReader) -> List[TrVectorSection]:
    """
    Read and parse track vector sections from a BlockReader.

    Consumes the `TrVectorSections` block and returns a list of TrVectorSection objects.

    Args:
        reader (BlockReader): Reader positioned at a track vector sections block.

    Returns:
        List[TrVectorSection]: The parsed track vector sections.
    """
    reader.verify_id(TokenID.TrVectorSections)

    tr_vector_sections: List[TrVectorSection] = []
    count = reader.read_uint()

    for _ in range(count):
        section_index = reader.read_uint()
        shape_index = reader.read_uint()
        wf_name_x = reader.read_int()
        wf_name_z = reader.read_int()
        wf_uid = reader.read_uint()
        flags1 = reader.read_flags()
        flags2 = reader.read_flags()
        _ = reader.read_string()
        tile_x = reader.read_int()
        tile_z = reader.read_int()
        x = reader.read_float()
        y = reader.read_float()
        z = reader.read_float()
        ax = reader.read_float()
        ay = reader.read_float()
        az = reader.read_float()

        tr_vector_section = TrVectorSection(
            flags1=flags1,
            flags2=flags2,
            section_index=section_index,
            shape_index=shape_index,
            tile_x=tile_x,
            tile_z=tile_z,
            x=x,
            y=y,
            z=z,
            ax=ax,
            ay=ay,
            az=az,
            wf_uid=wf_uid,
            wf_name_x=wf_name_x,
            wf_name_z=wf_name_z
        )
        tr_vector_sections.append(tr_vector_section)

    reader.skip()
    reader.verify_count(count, len(tr_vector_sections))

    return tr_vector_sections


def read_tr_item_refs(reader: BlockReader) -> List[int]:
    """
    Read and parse track item references from a BlockReader.

    Consumes the `TrItemRefs` block and returns a list of track item references.

    Args:
        reader (BlockReader): Reader positioned at a track item references block.

    Returns:
        List[int]: The parsed track item references.
    """
    reader.verify_id(TokenID.TrItemRefs)
    
    tr_item_refs: List[int] = []
    count = reader.read_uint()

    for sub_block in reader:
        sub_block.verify_id(TokenID.TrItemRef)

        tr_item_ref = sub_block.read_int()
        tr_item_refs.append(tr_item_ref)

    reader.skip()
    reader.verify_count(count, len(tr_item_refs))

    return tr_item_refs


def read_tr_pins(reader: BlockReader) -> List[TrPin]:
    """
    Read and parse track pins from a BlockReader.

    Consumes the `TrPins` block and returns a list of TrPin objects.

    Args:
        reader (BlockReader): Reader positioned at a track pins block.

    Returns:
        List[TrPin]: The parsed track pins.
    """
    reader.verify_id(TokenID.TrPins)

    tr_pins: List[int] = []

    for sub_block in reader:
        sub_block.verify_id(TokenID.TrPin)

        link = sub_block.read_int()
        direction = sub_block.read_int()

        tr_pins.append(TrPin(
            link=link,
            direction=direction
        ))

    reader.skip()

    return tr_pins


def read_tr_item_table(reader: BlockReader) -> List[TrItem]:
    """
    Read and parse track items from a BlockReader.

    Consumes the `TrItemTable` block and its child blocks, returning a list of TrItem objects.

    Args:
        reader (BlockReader): Reader positioned at a track item table block.

    Returns:
        List[TrItem]: The parsed track items.
    """
    with reader.sub_block(TokenID.TrItemTable) as tr_item_table_block:
        if tr_item_table_block is None:
            return []
        
        tr_items: List[TrItem] = []
        count = tr_item_table_block.read_uint()
        
        for sub_block in tr_item_table_block:
            tr_item = None

            if sub_block.id == TokenID.EmptyItem:
                tr_item = read_empty_item(sub_block)

            elif sub_block.id == TokenID.CrossoverItem:
                tr_item = read_crossover_item(sub_block)

            elif sub_block.id == TokenID.SignalItem:
                tr_item = read_signal_item(sub_block)

            elif sub_block.id == TokenID.SpeedPostItem:
                tr_item = read_speedpost_item(sub_block)

            elif sub_block.id == TokenID.SoundRegionItem:
                tr_item = read_soundregion_item(sub_block)

            elif sub_block.id == TokenID.LevelCrItem:
                tr_item = read_levelcr_item(sub_block)

            elif sub_block.id == TokenID.SidingItem:
                tr_item = read_siding_item(sub_block)

            elif sub_block.id == TokenID.PlatformItem:
                tr_item = read_platform_item(sub_block)

            elif sub_block.id == TokenID.HazzardItem:
                tr_item = read_hazzard_item(sub_block)

            elif sub_block.id == TokenID.PickupItem:
                tr_item = read_pickup_item(sub_block)

            elif sub_block.id == TokenID.CarSpawnerItem:
                tr_item = read_carspawner_item(sub_block)

            else:
                logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
                sub_block.skip()
            
            if tr_item is not None:
                tr_items.append(tr_item)

        tr_item_table_block.verify_count(count, len(tr_items))

        return tr_items


def read_empty_item(reader: BlockReader) -> EmptyItem:
    """
    Read and parse an empty item from a BlockReader.

    Consumes the `EmptyItem` block and returns an EmptyItem object.

    Args:
        reader (BlockReader): Reader positioned at an empty item block.

    Returns:
        EmptyItem: The parsed empty item.
    """
    reader.verify_id(TokenID.EmptyItem)

    empty_item = EmptyItem()
    
    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            empty_item = read_tr_item_id(sub_block, empty_item)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return empty_item


def read_crossover_item(reader: BlockReader) -> CrossoverItem:
    """
    Read and parse a crossover item from a BlockReader.

    Consumes the `CrossoverItem` block and its child blocks, returning a CrossoverItem object.

    Args:
        reader (BlockReader): Reader positioned at a crossover item block.

    Returns:
        CrossoverItem: The parsed crossover item.
    """
    reader.verify_id(TokenID.CrossoverItem)

    crossover_item = CrossoverItem()
    
    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            crossover_item = read_tr_item_id(sub_block, crossover_item)

        elif sub_block.id == TokenID.TrItemRData:
            crossover_item = read_tr_item_rdata(sub_block, crossover_item)

        elif sub_block.id == TokenID.TrItemPData:
            crossover_item = read_tr_item_pdata(sub_block, crossover_item)

        elif sub_block.id == TokenID.TrItemSData:
            crossover_item = read_tr_item_sdata(sub_block, crossover_item)

        elif sub_block.id == TokenID.CrossoverTrItemData:
            crossover_item.track_node = sub_block.read_uint()
            crossover_item.shape_index = sub_block.read_uint()
            sub_block.skip()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return crossover_item


def read_signal_item(reader: BlockReader) -> SignalItem:
    """
    Read and parse a signal item from a BlockReader.

    Consumes the `SignalItem` block and its child blocks, returning a SignalItem object.

    Args:
        reader (BlockReader): Reader positioned at a signal item block.

    Returns:
        SignalItem: The parsed signal item.
    """
    reader.verify_id(TokenID.SignalItem)

    signal_item = SignalItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            signal_item = read_tr_item_id(sub_block, signal_item)

        elif sub_block.id == TokenID.TrItemRData:
            signal_item = read_tr_item_rdata(sub_block, signal_item)

        elif sub_block.id == TokenID.TrItemPData:
            signal_item = read_tr_item_pdata(sub_block, signal_item)

        elif sub_block.id == TokenID.TrItemSData:
            signal_item = read_tr_item_sdata(sub_block, signal_item)

        elif sub_block.id == TokenID.TrSignalType:
            signal_item.flags = sub_block.read_flags()
            signal_item.direction = sub_block.read_uint()
            signal_item.signal_data1 = sub_block.read_float()
            signal_item.signal_type = sub_block.read_string()
            sub_block.skip()
        
        elif sub_block.id == TokenID.TrSignalDirs:
            signal_item.signal_dirs = read_signal_directions(sub_block)
            sub_block.skip()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return signal_item


def read_signal_directions(reader: BlockReader) -> List[SignalDirection]:
    """
    Read and parse signal directions from a BlockReader.

    Consumes the `TrSignalDirs` block and returns a list of SignalDirection objects.

    Args:
        reader (BlockReader): Reader positioned at a signal directions block.

    Returns:
        List[SignalDirection]: The parsed signal directions.
    """
    reader.verify_id(TokenID.TrSignalDirs)

    signal_directions: List[SignalDirection] = []
    count = reader.read_uint()

    for signal_direction_block in reader:
        signal_direction_block.verify_id(TokenID.TrSignalDir)

        track_node = signal_direction_block.read_uint()
        sd1 = signal_direction_block.read_uint()
        link_lr_path = signal_direction_block.read_uint()
        sd3 = signal_direction_block.read_uint()

        signal_direction_block.skip()

        signal_direction = SignalDirection(
            track_node=track_node,
            sd1=sd1,
            link_lr_path=link_lr_path,
            sd3=sd3
        )
        signal_directions.append(signal_direction)

    reader.skip()
    reader.verify_count(count, len(signal_directions))

    return signal_directions


def read_speedpost_item(reader: BlockReader) -> SpeedPostItem:
    """
    Read and parse a speed post item from a BlockReader.

    Consumes the `SpeedPostItem` block and its child blocks, returning a SpeedPostItem object.

    Args:
        reader (BlockReader): Reader positioned at a speed post item block.

    Returns:
        SpeedPostItem: The parsed speed post item.
    """
    reader.verify_id(TokenID.SpeedPostItem)

    speedpost_item = SpeedPostItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            speedpost_item = read_tr_item_id(sub_block, speedpost_item)

        elif sub_block.id == TokenID.TrItemRData:
            speedpost_item = read_tr_item_rdata(sub_block, speedpost_item)

        elif sub_block.id == TokenID.TrItemPData:
            speedpost_item = read_tr_item_pdata(sub_block, speedpost_item)

        elif sub_block.id == TokenID.TrItemSData:
            speedpost_item = read_tr_item_sdata(sub_block, speedpost_item)

        elif sub_block.id == TokenID.SpeedpostTrItemData:
            flags = sub_block.read_flags()
            speedpost_item.flags = flags

            is_warning = (flags & 1) != 0
            is_limit = (flags & (1 << 1)) != 0

            if not is_warning and not is_limit:
                speedpost_item.is_mile_post = True
            else:
                speedpost_item.is_warning = is_warning
                speedpost_item.is_limit = is_limit

                if is_warning and is_limit:
                    speedpost_item.is_warning = False
                    speedpost_item.is_resume = True

                if (flags & (1 << 5)) != 0:
                    speedpost_item.is_passenger = True

                if (flags & (1 << 6)) != 0:
                    speedpost_item.is_freight = True

                if (flags & (1 << 7)) != 0:
                    speedpost_item.is_passenger = True
                    speedpost_item.is_freight = True

                if (flags & (1 << 8)) != 0:
                    speedpost_item.is_mph = True

                if (flags & (1 << 4)) != 0:
                    speedpost_item.show_number = True

                    if (flags & (1 << 9)) != 0:
                        speedpost_item.show_dot = True

            if not speedpost_item.is_resume:
                if speedpost_item.is_mile_post and ((flags & (1 << 9)) == 0):
                    speedpost_item.speed_ind = float(math.trunc(sub_block.read_float()))
                else:
                    speedpost_item.speed_ind = sub_block.read_float()

            if speedpost_item.show_number:
                speedpost_item.display_number = sub_block.read_int()

            speedpost_item.angle = (sub_block.read_float() + math.pi) % (2 * math.pi) - math.pi

            sub_block.skip()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return speedpost_item


def read_soundregion_item(reader: BlockReader) -> SoundRegionItem:
    """
    Read and parse a sound region item from a BlockReader.

    Consumes the `SoundRegionItem` block and its child blocks, returning a SoundRegionItem object.

    Args:
        reader (BlockReader): Reader positioned at a sound region item block.

    Returns:
        SoundRegionItem: The parsed sound region item.
    """
    reader.verify_id(TokenID.SoundRegionItem)

    soundregion_item = SoundRegionItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            soundregion_item = read_tr_item_id(sub_block, soundregion_item)

        elif sub_block.id == TokenID.TrItemRData:
            soundregion_item = read_tr_item_rdata(sub_block, soundregion_item)

        elif sub_block.id == TokenID.TrItemPData:
            soundregion_item = read_tr_item_pdata(sub_block, soundregion_item)

        elif sub_block.id == TokenID.TrItemSData:
            soundregion_item = read_tr_item_sdata(sub_block, soundregion_item)

        elif sub_block.id == TokenID.TrItemSRData:
            soundregion_item.sr_data1 = sub_block.read_uint()
            soundregion_item.sr_data2 = sub_block.read_uint()
            soundregion_item.sr_data3 = sub_block.read_float()
            sub_block.skip()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return soundregion_item


def read_levelcr_item(reader: BlockReader) -> LevelCrItem:
    """
    Read and parse a level crossing item from a BlockReader.

    Consumes the `LevelCrItem` block and its child blocks, returning a LevelCrItem object.

    Args:
        reader (BlockReader): Reader positioned at a level crossing item block.

    Returns:
        LevelCrItem: The parsed level crossing item.
    """
    reader.verify_id(TokenID.LevelCrItem)

    levelcr_item = LevelCrItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            levelcr_item = read_tr_item_id(sub_block, levelcr_item)

        elif sub_block.id == TokenID.TrItemRData:
            levelcr_item = read_tr_item_rdata(sub_block, levelcr_item)

        elif sub_block.id == TokenID.TrItemPData:
            levelcr_item = read_tr_item_pdata(sub_block, levelcr_item)

        elif sub_block.id == TokenID.TrItemSData:
            levelcr_item = read_tr_item_sdata(sub_block, levelcr_item)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return levelcr_item


def read_siding_item(reader: BlockReader) -> SidingItem:
    """
    Read and parse a siding item from a BlockReader.

    Consumes the `SidingItem` block and its child blocks, returning a SidingItem object.

    Args:
        reader (BlockReader): Reader positioned at a siding item block.

    Returns:
        SidingItem: The parsed siding item.
    """
    reader.verify_id(TokenID.SidingItem)

    siding_item = SidingItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            siding_item = read_tr_item_id(sub_block, siding_item)

        elif sub_block.id == TokenID.TrItemRData:
            siding_item = read_tr_item_rdata(sub_block, siding_item)

        elif sub_block.id == TokenID.TrItemPData:
            siding_item = read_tr_item_pdata(sub_block, siding_item)

        elif sub_block.id == TokenID.TrItemSData:
            siding_item = read_tr_item_sdata(sub_block, siding_item)

        elif sub_block.id == TokenID.SidingTrItemData:
            siding_item.flags = sub_block.read_flags()
            siding_item.linked_siding_item_id = sub_block.read_uint()
            sub_block.skip()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return siding_item


def read_platform_item(reader: BlockReader) -> PlatformItem:
    """
    Read and parse a platform item from a BlockReader.

    Consumes the `PlatformItem` block and its child blocks, returning a PlatformItem object.

    Args:
        reader (BlockReader): Reader positioned at a platform item block.

    Returns:
        PlatformItem: The parsed platform item.
    """
    reader.verify_id(TokenID.PlatformItem)

    platform_item = PlatformItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            platform_item = read_tr_item_id(sub_block, platform_item)

        elif sub_block.id == TokenID.TrItemRData:
            platform_item = read_tr_item_rdata(sub_block, platform_item)

        elif sub_block.id == TokenID.TrItemPData:
            platform_item = read_tr_item_pdata(sub_block, platform_item)

        elif sub_block.id == TokenID.TrItemSData:
            platform_item = read_tr_item_sdata(sub_block, platform_item)

        elif sub_block.id == TokenID.PlatformName:
            platform_item.name = sub_block.read_string()
            sub_block.skip()

        elif sub_block.id == TokenID.Station:
            platform_item.station = sub_block.read_string()
            sub_block.skip()

        elif sub_block.id == TokenID.PlatformMinWaitingTime:
            platform_item.min_waiting_time = sub_block.read_uint()
            sub_block.skip()

        elif sub_block.id == TokenID.PlatformNumPassengersWaiting:
            platform_item.num_passengers_waiting = sub_block.read_uint()
            sub_block.skip()

        elif sub_block.id == TokenID.PlatformTrItemData:
            platform_item.flags = sub_block.read_flags()
            platform_item.linked_platform_item_id = sub_block.read_uint()
            sub_block.skip()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return platform_item


def read_hazzard_item(reader: BlockReader) -> HazzardItem:
    """
    Read and parse a hazzard item from a BlockReader.

    Consumes the `HazzardItem` block and its child blocks, returning a HazzardItem object.

    Args:
        reader (BlockReader): Reader positioned at a hazzard item block.

    Returns:
        HazzardItem: The parsed hazzard item.
    """
    reader.verify_id(TokenID.HazzardItem)

    hazzard_item = HazzardItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            hazzard_item = read_tr_item_id(sub_block, hazzard_item)

        elif sub_block.id == TokenID.TrItemRData:
            hazzard_item = read_tr_item_rdata(sub_block, hazzard_item)

        elif sub_block.id == TokenID.TrItemPData:
            hazzard_item = read_tr_item_pdata(sub_block, hazzard_item)

        elif sub_block.id == TokenID.TrItemSData:
            hazzard_item = read_tr_item_sdata(sub_block, hazzard_item)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return hazzard_item


def read_pickup_item(reader: BlockReader) -> PickupItem:
    """
    Read and parse a pickup item from a BlockReader.

    Consumes the `PickupItem` block and its child blocks, returning a PickupItem object.

    Args:
        reader (BlockReader): Reader positioned at a pickup item block.

    Returns:
        PickupItem: The parsed pickup item.
    """
    reader.verify_id(TokenID.PickupItem)

    pickup_item = PickupItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            pickup_item = read_tr_item_id(sub_block, pickup_item)

        elif sub_block.id == TokenID.TrItemRData:
            pickup_item = read_tr_item_rdata(sub_block, pickup_item)

        elif sub_block.id == TokenID.TrItemPData:
            pickup_item = read_tr_item_pdata(sub_block, pickup_item)

        elif sub_block.id == TokenID.TrItemSData:
            pickup_item = read_tr_item_sdata(sub_block, pickup_item)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return pickup_item


def read_carspawner_item(reader: BlockReader) -> CarSpawnerItem:
    """
    Read and parse a car spawner item from a BlockReader.

    Consumes the `CarSpawnerItem` block and its child blocks, returning a CarSpawnerItem object.

    Args:
        reader (BlockReader): Reader positioned at a car spawner item block.

    Returns:
        CarSpawnerItem: The parsed car spawner item.
    """
    reader.verify_id(TokenID.CarSpawnerItem)

    carspawner_item = CarSpawnerItem()

    for sub_block in reader:
        if sub_block.id == TokenID.TrItemId:
            carspawner_item = read_tr_item_id(sub_block, carspawner_item)

        elif sub_block.id == TokenID.TrItemRData:
            carspawner_item = read_tr_item_rdata(sub_block, carspawner_item)

        elif sub_block.id == TokenID.TrItemSData:
            carspawner_item = read_tr_item_sdata(sub_block, carspawner_item)
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return carspawner_item


def read_tr_item_id(reader: BlockReader, tr_item: TrItem) -> TrItem:
    """
    Read and parse track item ID data from a BlockReader.

    Consumes the `TrItemId` block and updates a TrItem object.

    Args:
        reader (BlockReader): Reader positioned at a track item ID block.
        tr_item (TrItem): Track item to update.

    Returns:
        TrItem: The updated track item.
    """
    reader.verify_id(TokenID.TrItemId)

    tr_item.item_id = reader.read_uint()

    reader.skip()

    return tr_item


def read_tr_item_rdata(reader: BlockReader, tr_item: TrItem) -> TrItem:
    """
    Read and parse track item rdata from a BlockReader.

    Consumes the `TrItemRData` block and updates a TrItem object.

    Args:
        reader (BlockReader): Reader positioned at a track item rdata block.
        tr_item (TrItem): Track item to update.

    Returns:
        TrItem: The updated track item.
    """
    reader.verify_id(TokenID.TrItemRData)

    tr_item.x = reader.read_float()
    tr_item.y = reader.read_float()
    tr_item.z = reader.read_float()
    tr_item.tile_x = reader.read_int()
    tr_item.tile_z = reader.read_int()

    reader.skip()

    return tr_item


def read_tr_item_pdata(reader: BlockReader, tr_item: TrItem) -> TrItem:
    """
    Read and parse track item pdata from a BlockReader.

    Consumes the `TrItemPData` block and updates a TrItem object.

    Args:
        reader (BlockReader): Reader positioned at a track item pdata block.
        tr_item (TrItem): Track item to update.

    Returns:
        TrItem: The updated track item.
    """
    reader.verify_id(TokenID.TrItemPData)

    tr_item.px = reader.read_float()
    tr_item.pz = reader.read_float()
    tr_item.tile_px = reader.read_int()
    tr_item.tile_pz = reader.read_int()

    reader.skip()

    return tr_item


def read_tr_item_sdata(reader: BlockReader, tr_item: TrItem) -> TrItem:
    """
    Read and parse track item sdata from a BlockReader.

    Consumes the `TrItemSData` block and updates a TrItem object.

    Args:
        reader (BlockReader): Reader positioned at a track item sdata block.
        tr_item (TrItem): Track item to update.

    Returns:
        TrItem: The updated track item.
    """
    reader.verify_id(TokenID.TrItemSData)

    tr_item.sdata1 = reader.read_float()
    tr_item.sdata2 = reader.read_flags()

    reader.skip()

    return tr_item