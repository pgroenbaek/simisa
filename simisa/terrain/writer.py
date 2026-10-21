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
from .models import *


def dump(
    terrain: Terrain,
    filepath: str,
    binary: bool = False,
    ascii: bool = False,
    compressed: bool = False,
    verbose: Verbose = None
) -> None:
    """
    Write a terrain object to disk.

    This function supports both compressed/uncompressed as well as binary/text data.
    It writes the terrain data to the file at the given path.

    Args:
        terrain (Terrain): The terrain object to write.
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
        ("terrain", terrain, Terrain),
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
        filetype="t",
        fileversion=6,
        is_binary=binary,
        is_utf16le=not ascii and not binary and not compressed,
        is_compressed=compressed,
        verbose=verbose
    ) as writer:
        write_terrain(writer, terrain)


def dumps(terrain: Terrain, verbose: Verbose = None) -> str:
    """
    Write a terrain object to a string.

    This function does not support binary or compressed data. It writes terrain
    data to a string and returns it.

    Args:
        terrain (Terrain): The terrain object to write.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        str: The string containing the terrain data.

    Raises:
        TypeError: If `terrain` is not a Terrain object.
    """
    if not isinstance(terrain, Terrain):
        raise TypeError(f"Parameter 'terrain' must be Terrain, but got {type(terrain).__name__}")

    terrain_text = BlockWriter.to_string(
        lambda writer: write_terrain(writer, terrain),
        filetype="t",
        fileversion=6,
        verbose=verbose
    )

    return terrain_text


DEFAULT_LIST = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_count=True,
    newline_before_closing=True,
    newline_after_closing=True
)

TERRAIN_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_start=True,
    newline_before_closing=True
)

TERRAIN_SAMPLES_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

TERRAIN_SHADER_BLOCK = BlockFormat(
    newline_before_closing=True
)

TERRAIN_PATCHES_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

TERRAIN_PATCHSET_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

TERRAIN_PATCHSET_PATCHES_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)


def write_terrain(writer: BlockWriter, terrain: Terrain) -> None:
    """
    Write a terrain block to a BlockWriter.

    Writes the `terrain` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the terrain block to.
        terrain (Terrain): The terrain object to write.
    """
    with writer.sub_block(TokenID.terrain, block_format=TERRAIN_BLOCK) as terrain_block:
        with terrain_block.sub_block(TokenID.terrain_errthreshold_scale) as errthreshold_scale_block:
            errthreshold_scale_block.write_float(terrain.terrain_errthreshold_scale)

        if terrain.terrain_water_height_offset is not None:
            write_terrain_water_height_offset(terrain_block, terrain.terrain_water_height_offset)

        if terrain.terrain_alwaysselect_maxdist is not None:
            with terrain_block.sub_block(TokenID.terrain_alwaysselect_maxdist) as alwaysselect_maxdist_block:
                alwaysselect_maxdist_block.write_float(terrain.terrain_alwaysselect_maxdist)

        if terrain.terrain_samples is not None:
            write_terrain_samples(terrain_block, terrain.terrain_samples)

        if terrain.terrain_shaders is not None:
            write_terrain_shaders(terrain_block, terrain.terrain_shaders)

        if terrain.terrain_patchsets is not None:
            with terrain_block.sub_block(TokenID.terrain_patches, block_format=TERRAIN_PATCHES_BLOCK) as terrain_patches_block:
                write_terrain_patchsets(terrain_patches_block, terrain.terrain_patchsets)


def write_terrain_water_height_offset(writer: BlockWriter, offset: TerrainWaterHeightOffset) -> None:
    """
    Write a terrain water height offset block to a BlockWriter.

    Writes the `terrain_water_height_offset` sub-block.

    Args:
        writer (BlockWriter): Writer to write the terrain water height offset block to.
        offset (TerrainWaterHeightOffset): The terrain water height offset object to write.
    """
    if not isinstance(offset, TerrainWaterHeightOffset):
        raise TypeError(f"Terrain property 'terrain_water_height_offset' must be TerrainWaterHeightOffset, but got {type(offset).__name__}")

    with writer.sub_block(TokenID.terrain_water_height_offset) as water_height_offset_block:
        if offset.sw is not None:
            water_height_offset_block.write_float(offset.sw)

        if offset.se is not None:
            water_height_offset_block.write_float(offset.se)

        if offset.ne is not None:
            water_height_offset_block.write_float(offset.ne)
        
        if offset.nw is not None:
            water_height_offset_block.write_float(offset.nw)


def write_terrain_samples(writer: BlockWriter, samples: TerrainSamples) -> None:
    """
    Write terrain samples to a BlockWriter.

    Writes the `terrain_samples` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the terrain samples block to.
        samples (TerrainSamples): The terrain samples object to write.
    """
    if not isinstance(samples, TerrainSamples):
        raise TypeError(f"Terrain property 'terrain_samples' must be TerrainSamples, but got {type(samples).__name__}")

    with writer.sub_block(TokenID.terrain_samples, block_format=TERRAIN_SAMPLES_BLOCK) as samples_block:
        if samples.terrain_nsamples is not None:
            with samples_block.sub_block(TokenID.terrain_nsamples) as nsamples_block:
                nsamples_block.write_int(samples.terrain_nsamples)
        
        if samples.terrain_sample_rotation is not None:
            with samples_block.sub_block(TokenID.terrain_sample_rotation) as sample_rotation_block:
                sample_rotation_block.write_float(samples.terrain_sample_rotation)
        
        if samples.terrain_sample_floor is not None:
            with samples_block.sub_block(TokenID.terrain_sample_floor) as sample_floor_block:
                sample_floor_block.write_float(samples.terrain_sample_floor)
        
        if samples.terrain_sample_scale is not None:
            with samples_block.sub_block(TokenID.terrain_sample_scale) as sample_scale_block:
                sample_scale_block.write_float(samples.terrain_sample_scale)
        
        if samples.terrain_sample_size is not None:
            with samples_block.sub_block(TokenID.terrain_sample_size) as sample_size_block:
                sample_size_block.write_float(samples.terrain_sample_size)
        
        if samples.terrain_sample_ybuffer is not None:
            with samples_block.sub_block(TokenID.terrain_sample_ybuffer) as sample_ybuffer_block:
                sample_ybuffer_block.write_string(samples.terrain_sample_ybuffer)
        
        if samples.terrain_sample_ebuffer is not None:
            with samples_block.sub_block(TokenID.terrain_sample_ebuffer) as sample_ebuffer_block:
                sample_ebuffer_block.write_string(samples.terrain_sample_ebuffer)
        
        if samples.terrain_sample_nbuffer is not None:
            with samples_block.sub_block(TokenID.terrain_sample_nbuffer) as sample_nbuffer_block:
                sample_nbuffer_block.write_string(samples.terrain_sample_nbuffer)


def write_terrain_shaders(writer: BlockWriter, shaders: List[TerrainShader]) -> None:
    """
    Write terrain shaders to a BlockWriter.

    Writes the `terrain_shaders` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the terrain shaders block to.
        shaders (List[TerrainShader]): List of terrain shader objects to write.
    """
    for shader in shaders:
        if not isinstance(shader, TerrainShader):
            raise TypeError(f"Terrain property 'terrain_shaders' must contain TerrainShader objects, but got {type(shader).__name__}")

    with writer.sub_block(TokenID.terrain_shaders, block_format=DEFAULT_LIST) as shaders_block:
        shaders_block.write_count(len(shaders))

        for shader in shaders:
            with shaders_block.sub_block(TokenID.terrain_shader, block_format=TERRAIN_SHADER_BLOCK) as shader_block:
                shader_block.write_string(shader.shader_name)

                if shader.terrain_texslots:
                    write_terrain_texslots(shader_block, shader.terrain_texslots)
                
                if shader.terrain_uvcalcs:
                    write_terrain_uvcalcs(shader_block, shader.terrain_uvcalcs)


def write_terrain_texslots(writer: BlockWriter, texslots: List[TerrainTexslot]) -> None:
    """
    Write terrain texture slots to a BlockWriter.

    Writes the `terrain_texslots` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the terrain texture slots block to.
        texslots (List[TerrainTexslot]): List of terrain texture slot objects to write.
    """
    for texslot in texslots:
        if not isinstance(texslot, TerrainTexslot):
            raise TypeError(f"TerrainShader property 'terrain_texslots' must contain TerrainTexslot objects, but got {type(texslot).__name__}")

    with writer.sub_block(TokenID.terrain_texslots, block_format=DEFAULT_LIST) as texslots_block:
        texslots_block.write_count(len(texslots))

        for texslot in texslots:
            with texslots_block.sub_block(TokenID.terrain_texslot) as texslot_block:
                texslot_block.write_string(texslot.filename)
                texslot_block.write_int(texslot.a)
                texslot_block.write_int(texslot.b)


def write_terrain_uvcalcs(writer: BlockWriter, uvcalcs: List[TerrainUVCalc]) -> None:
    """
    Write terrain UV calculations to a BlockWriter.

    Writes the `terrain_uvcalcs` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the terrain UV calculations block to.
        uvcalcs (List[TerrainUVCalc]): List of terrain UV calculation objects to write.
    """
    for uvcalc in uvcalcs:
        if not isinstance(uvcalc, TerrainUVCalc):
            raise TypeError(f"TerrainShader property 'terrain_uvcalcs' must contain TerrainUVCalc objects, but got {type(uvcalc).__name__}")

    with writer.sub_block(TokenID.terrain_uvcalcs, block_format=DEFAULT_LIST) as uvcalcs_block:
        uvcalcs_block.write_count(len(uvcalcs))

        for uvcalc in uvcalcs:
            with uvcalcs_block.sub_block(TokenID.terrain_uvcalc) as uvcalc_block:
                uvcalc_block.write_int(uvcalc.a)
                uvcalc_block.write_int(uvcalc.b)
                uvcalc_block.write_int(uvcalc.c)
                uvcalc_block.write_float(float(uvcalc.d))


def write_terrain_patchsets(writer: BlockWriter, patchsets: List[TerrainPatchset]) -> None:
    """
    Write terrain patchsets to a BlockWriter.

    Writes the `terrain_patchsets` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the terrain patchsets block to.
        patchsets (List[TerrainPatchset]): List of terrain patchset objects to write.
    """
    for patchset in patchsets:
        if not isinstance(patchset, TerrainPatchset):
            raise TypeError(f"Terrain property 'terrain_patchsets' must contain TerrainPatchset objects, but got {type(patchset).__name__}")

    with writer.sub_block(TokenID.terrain_patchsets, block_format=DEFAULT_LIST) as patchsets_block:
        patchsets_block.write_count(len(patchsets))

        for patchset in patchsets:
            with patchsets_block.sub_block(TokenID.terrain_patchset, block_format=TERRAIN_PATCHSET_BLOCK) as patchset_block:
                with patchset_block.sub_block(TokenID.terrain_patchset_distance) as patchset_distance_block:
                    patchset_distance_block.write_int(patchset.terrain_patchset_distance)
                
                with patchset_block.sub_block(TokenID.terrain_patchset_npatches) as patchset_npatches_block:
                    patchset_npatches_block.write_int(patchset.terrain_patchset_npatches)
                
                write_terrain_patchset_patches(patchset_block, patchset.terrain_patchset_patches)


def write_terrain_patchset_patches(writer: BlockWriter, patches: List[TerrainPatchsetPatch]) -> None:
    """
    Write terrain patchset patches to a BlockWriter.

    Writes the `terrain_patchset_patches` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the terrain patchset patches block to.
        patches (List[TerrainPatchsetPatch]): List of terrain patchset patch objects to write.
    """
    for patch in patches:
        if not isinstance(patch, TerrainPatchsetPatch):
            raise TypeError(f"TerrainPatchset property 'patches' must contain TerrainPatchsetPatch objects, but got {type(patch).__name__}")

    with writer.sub_block(TokenID.terrain_patchset_patches, block_format=TERRAIN_PATCHSET_PATCHES_BLOCK) as patchset_patches_block:
        for patch in patches:
            with patchset_patches_block.sub_block(TokenID.terrain_patchset_patch) as patchset_patch_block:
                patchset_patch_block.write_flags(patch.flags)
                patchset_patch_block.write_float(patch.center_x)
                patchset_patch_block.write_float(patch.average_y)
                patchset_patch_block.write_float(patch.center_z)
                patchset_patch_block.write_float(patch.factor_y)
                patchset_patch_block.write_float(patch.range_y)
                patchset_patch_block.write_float(patch.radius_m)
                patchset_patch_block.write_int(patch.shader_index)
                patchset_patch_block.write_float(patch.x)
                patchset_patch_block.write_float(patch.y)
                patchset_patch_block.write_float(patch.w)
                patchset_patch_block.write_float(patch.b)
                patchset_patch_block.write_float(patch.c)
                patchset_patch_block.write_float(patch.h)
                patchset_patch_block.write_float(patch.error_bias)