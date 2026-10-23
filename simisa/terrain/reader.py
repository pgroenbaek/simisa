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
) -> Terrain:
    """
    Load and parse a terrain file from disk.

    This function supports both compressed/uncompressed as well as binary/text data.
    It opens the file at the given path, validates that it is a supported shape
    file based on its subheader, and returns a parsed Terrain object.

    Args:
        filepath (str): Path to the terrain file.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        Terrain: The parsed terrain object.

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

        if not reader.filetype == 't':
            raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a terrain file?")

        return read_terrain(reader)


def loads(
    terrain_text: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> Terrain:
    """
    Parse terrain from a string containing terrain data.

    This function does not support binary or compressed data. It reads terrain
    data from the provided string, validates that it represents a supported
    terrain file based on its subheader, and returns a parsed Terrain object.

    Args:
        terrain_text (str): String containing terrain file data.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        Terrain: The parsed terrain object.

    Raises:
        TypeError: If a parameter is not of the expected type.
        SimisaHeaderError: If the data has an invalid or unrecognized SIMISA header.
        SimisaSubheaderError: If the data has an invalid or unrecognized SIMISA subheader.
        BlockReaderError: If the block reader encounters an error or malformed data.
        StfReaderError: If the STF reader encounters an error or malformed data.
        UnresolvableIncludeError: If includes within the file cannot be resolved.
    """
    if not isinstance(terrain_text, str):
        raise TypeError(f"Parameter 'terrain_text' must be str, but got {type(terrain_text).__name__}")

    reader = BlockReader.from_string(terrain_text, progress=progress, verbose=verbose)

    if not reader.filetype == 't':
        raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a terrain file?")

    return read_terrain(reader)


def read_terrain(reader: BlockReader) -> Terrain:
    """
    Read and parse a terrain block from a BlockReader.

    Consumes the `terrain` sub-block and its child blocks, returning a fully
    constructed Terrain object.

    Args:
        reader (BlockReader): Reader positioned at a terrain block.

    Returns:
        Terrain: The parsed terrain.
    """
    reader.report_progress("Reading terrain data...")

    with reader.sub_block(TokenID.terrain) as terrain_block:
        terrain = Terrain()

        for sub_block in terrain_block:
            if sub_block.id == TokenID.terrain_errthreshold_scale:
                terrain.terrain_errthreshold_scale = sub_block.read_float()
            
            elif sub_block.id == TokenID.terrain_water_height_offset:
                terrain.terrain_water_height_offset = read_terrain_water_height_offset(sub_block)
            
            elif sub_block.id == TokenID.terrain_alwaysselect_maxdist:
                terrain.terrain_alwaysselect_maxdist = sub_block.read_float()
            
            elif sub_block.id == TokenID.terrain_samples:
                terrain.terrain_samples = read_terrain_samples(sub_block)
            
            elif sub_block.id == TokenID.terrain_shaders:
                terrain.terrain_shaders = read_terrain_shaders(sub_block)
            
            elif sub_block.id == TokenID.terrain_patches:
                terrain.terrain_patchsets = read_terrain_patchsets(sub_block)
            
            else:
                logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
                sub_block.skip()

        return terrain


def read_terrain_water_height_offset(reader: BlockReader) -> TerrainWaterHeightOffset:
    """
    Read and parse a terrain water height offset from a BlockReader.

    Consumes the `terrain_water_height_offset` block and returns a TerrainWaterHeightOffset object.

    Args:
        reader (BlockReader): Reader positioned at a terrain water height offset block.

    Returns:
        TerrainWaterHeightOffset: The parsed water height offsets.
    """
    reader.verify_id(TokenID.terrain_water_height_offset)

    water_height_offset = TerrainWaterHeightOffset()

    if not reader.end_of_block():
        water_height_offset.sw = reader.read_float()

    if not reader.end_of_block():
        water_height_offset.se = reader.read_float()

    if not reader.end_of_block():
        water_height_offset.ne = reader.read_float()

    if not reader.end_of_block():
        water_height_offset.nw = reader.read_float()
    
    return water_height_offset


def read_terrain_samples(reader: BlockReader) -> TerrainSamples:
    """
    Read and parse terrain samples from a BlockReader.

    Consumes the `terrain_samples` sub-block and returns a TerrainSamples object.

    Args:
        reader (BlockReader): Reader positioned at a terrain samples block.

    Returns:
        TerrainSamples: The parsed terrain samples.
    """
    reader.verify_id(TokenID.terrain_samples)

    terrain_samples = TerrainSamples()
    
    for sub_block in reader:
        if sub_block.id == TokenID.terrain_nsamples:
            terrain_samples.terrain_nsamples = sub_block.read_int()
        
        elif sub_block.id == TokenID.terrain_sample_rotation:
            terrain_samples.terrain_sample_rotation = sub_block.read_float()
        
        elif sub_block.id == TokenID.terrain_sample_floor:
            terrain_samples.terrain_sample_floor = sub_block.read_float()
        
        elif sub_block.id == TokenID.terrain_sample_scale:
            terrain_samples.terrain_sample_scale = sub_block.read_float()
        
        elif sub_block.id == TokenID.terrain_sample_size:
            terrain_samples.terrain_sample_size = sub_block.read_float()
        
        elif sub_block.id == TokenID.terrain_sample_ybuffer:
            terrain_samples.terrain_sample_ybuffer = sub_block.read_string()
        
        elif sub_block.id == TokenID.terrain_sample_ebuffer:
            terrain_samples.terrain_sample_ebuffer = sub_block.read_string()
        
        elif sub_block.id == TokenID.terrain_sample_nbuffer:
            terrain_samples.terrain_sample_nbuffer = sub_block.read_string()
        
        else:
            logger.warning(f"Unhandled sub block: {sub_block.id.name} (id: {sub_block.id})")
            sub_block.skip()

    return terrain_samples


def read_terrain_shaders(reader: BlockReader) -> List[TerrainShader]:
    """
    Read and parse terrain shaders from a BlockReader.

    Consumes the `terrain_shaders` sub-block and returns a list of TerrainShader objects.

    Args:
        reader (BlockReader): Reader positioned at a terrain shaders block.

    Returns:
        List[TerrainShader]: The parsed terrain shaders.
    """
    reader.verify_id(TokenID.terrain_shaders)

    terrain_shaders: List[TerrainShader] = []
    count = reader.read_int()
    
    for shader_block in reader:
        shader_block.verify_id(TokenID.terrain_shader)

        shader_name = shader_block.read_string()
        
        terrain_texslots: List[TerrainTexslot] = []
        terrain_uvcalcs: List[TerrainUVCalc] = []

        for shader_sub_block in shader_block:
            if shader_sub_block.id == TokenID.terrain_texslots:
                terrain_texslots = read_terrain_texslots(shader_sub_block)

            elif shader_sub_block.id == TokenID.terrain_uvcalcs:
                terrain_uvcalcs = read_terrain_uvcalcs(shader_sub_block)
            
            else:
                logger.warning(f"Unhandled sub block: {shader_sub_block.id.name} (id: {shader_sub_block.id})")
                shader_sub_block.skip()
        
        terrain_shader = TerrainShader(
            shader_name=shader_name,
            terrain_texslots=terrain_texslots,
            terrain_uvcalcs=terrain_uvcalcs
        )
        terrain_shaders.append(terrain_shader)
    
    reader.verify_count(count, len(terrain_shaders))
    
    if not reader.end_of_block():
        reader.skip()
    
    return terrain_shaders


def read_terrain_texslots(reader: BlockReader) -> List[TerrainTexslot]:
    """
    Read and parse terrain texslots from a BlockReader.

    Consumes the `terrain_texslots` sub-block and returns a list of TerrainTexslot objects.

    Args:
        reader (BlockReader): Reader positioned at a terrain texslots block.

    Returns:
        List[TerrainTexslot]: The parsed terrain texslots.
    """
    reader.verify_id(TokenID.terrain_texslots)

    terrain_texslots: List[TerrainTexslot] = []
    count = reader.read_uint()
    
    for texslot_block in reader:
        texslot_block.verify_id(TokenID.terrain_texslot)

        filename = texslot_block.read_string()
        a = texslot_block.read_int()
        b = texslot_block.read_int()
        texslot_block.skip()

        terrain_texslot = TerrainTexslot(
            filename=filename,
            a=a,
            b=b
        )
        terrain_texslots.append(terrain_texslot)
    
    reader.verify_count(count, len(terrain_texslots))
    
    return terrain_texslots


def read_terrain_uvcalcs(reader: BlockReader) -> List[TerrainUVCalc]:
    """
    Read and parse terrain UV calculations from a BlockReader.

    Consumes the `terrain_uvcalcs` sub-block and returns a list of TerrainUVCalc objects.

    Args:
        reader (BlockReader): Reader positioned at a terrain UV calculations block.

    Returns:
        List[TerrainUVCalc]: The parsed terrain UV calculations.
    """
    reader.verify_id(TokenID.terrain_uvcalcs)

    terrain_uvcalcs: List[TerrainUVCalc] = []
    count = reader.read_uint()
    
    for uvcalc_block in reader:
        uvcalc_block.verify_id(TokenID.terrain_uvcalc)

        a = uvcalc_block.read_int()
        b = uvcalc_block.read_int()
        c = uvcalc_block.read_int()
        d = int(uvcalc_block.read_float())
        uvcalc_block.skip()

        terrain_uvcalc = TerrainUVCalc(
            a=a,
            b=b,
            c=c,
            d=d
        )
        terrain_uvcalcs.append(terrain_uvcalc)
    
    reader.verify_count(count, len(terrain_uvcalcs))
    
    if not reader.end_of_block():
        reader.skip()
    
    return terrain_uvcalcs


def read_terrain_patchsets(reader: BlockReader) -> List[TerrainPatchset]:
    """
    Read and parse terrain patchsets from a BlockReader.

    Consumes the `terrain_patchsets` sub-block and returns a list of TerrainPatchset objects.

    Args:
        reader (BlockReader): Reader positioned at a terrain patchsets block.

    Returns:
        List[TerrainPatchset]: The parsed terrain patchsets.
    """
    reader.report_progress("Reading terrain patches...")

    with reader.sub_block(TokenID.terrain_patchsets) as patchsets_block:
        terrain_patchsets: List[TerrainPatchset] = []
        count = patchsets_block.read_int()

        for patchset_block in patchsets_block:
            patchset_block.verify_id(TokenID.terrain_patchset)

            terrain_patchset_distance: int = 0
            terrain_patchset_npatches: int = 0
            terrain_patchset_patches: List[TerrainPatchsetPatch] = []

            for patchset_sub_block in patchset_block:
                if patchset_sub_block.id == TokenID.terrain_patchset_distance:
                    terrain_patchset_distance = patchset_sub_block.read_int()

                elif patchset_sub_block.id == TokenID.terrain_patchset_npatches:
                    terrain_patchset_npatches = patchset_sub_block.read_int()

                elif patchset_sub_block.id == TokenID.terrain_patchset_patches: 
                    terrain_patchset_patches = read_terrain_patchset_patches(patchset_sub_block)
                
                else:
                    logger.warning(f"Unhandled sub block: {patchset_sub_block.id.name} (id: {patchset_sub_block.id})")
                    patchset_sub_block.skip()
            
            terrain_patchset = TerrainPatchset(
                terrain_patchset_distance=terrain_patchset_distance,
                terrain_patchset_npatches=terrain_patchset_npatches,
                terrain_patchset_patches=terrain_patchset_patches
            )
            terrain_patchsets.append(terrain_patchset)
        
        reader.verify_count(count, len(terrain_patchsets))
            
        if not reader.end_of_block():
            reader.skip()
        
    return terrain_patchsets


def read_terrain_patchset_patches(reader: BlockReader) -> List[TerrainPatchsetPatch]:
    """
    Read and parse terrain patchset patches from a BlockReader.

    Consumes the `terrain_patchset_patches` sub-block and returns a list of TerrainPatchsetPatch objects.

    Args:
        reader (BlockReader): Reader positioned at a terrain patchset patches block.

    Returns:
        List[TerrainPatchsetPatch]: The parsed terrain patchset patches.
    """
    reader.verify_id(TokenID.terrain_patchset_patches)

    patchset_patches: List[TerrainPatchsetPatch] = []
    
    for patchset_patch_block in reader:
        patchset_patch_block.verify_id(TokenID.terrain_patchset_patch)

        flags = patchset_patch_block.read_flags()
        center_x = patchset_patch_block.read_float()
        average_y = patchset_patch_block.read_float()
        center_z = patchset_patch_block.read_float()
        factor_y = patchset_patch_block.read_float()
        range_y = patchset_patch_block.read_float()
        radius_m = patchset_patch_block.read_float()
        shader_index = patchset_patch_block.read_int()
        x = patchset_patch_block.read_float()
        y = patchset_patch_block.read_float()
        w = patchset_patch_block.read_float()
        b = patchset_patch_block.read_float()
        c = patchset_patch_block.read_float()
        h = patchset_patch_block.read_float()
        error_bias = patchset_patch_block.read_float()

        patchset_patch = TerrainPatchsetPatch(
            flags=flags,
            center_x=center_x,
            center_z=center_z,
            average_y=average_y,
            range_y=range_y,
            factor_y=factor_y,
            shader_index=shader_index,
            error_bias=error_bias,
            x=x,
            y=y,
            w=w,
            h=h,
            b=b,
            c=c,
            radius_m=radius_m
        )
        patchset_patches.append(patchset_patch)
    
    return patchset_patches