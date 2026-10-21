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
from .models import *


def dump(
    shape: Shape,
    filepath: str,
    binary: bool = False,
    ascii: bool = False,
    compressed: bool = False
) -> None:
    """
    Write a shape object to disk.

    This function supports both compressed/uncompressed as well as binary/text data.
    It writes the shape data to the file at the given path.

    Args:
        shape (Shape): The shape object to write.
        filepath (str): Path to the output file.
        binary (bool): Whether to write binary data. Defaults to False.
        ascii (bool): Whether to write ASCII data. Defaults to False. Always True when binary or compressed.
        compressed (bool): Whether to write compressed data. Defaults to False.

    Raises:
        TypeError: If any parameter has an unexpected type.
        OSError: If the file cannot be written.
    """
    check_params = (
        ("shape", shape, Shape),
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
        filetype="s",
        fileversion=1,
        is_binary=binary,
        is_utf16le=not ascii and not binary and not compressed,
        is_compressed=compressed
    ) as writer:
        write_shape(writer, shape)


def dumps(shape: Shape) -> str:
    """
    Write a shape object to a string.

    This function does not support binary or compressed data. It writes shape
    data to a string and returns it.

    Args:
        shape (Shape): The shape object to write.

    Returns:
        str: The string containing the shape data.

    Raises:
        TypeError: If `shape` is not a Shape object.
    """
    if not isinstance(shape, Shape):
        raise TypeError(f"Parameter 'shape' must be Shape, but got {type(shape).__name__}")

    shape_text = BlockWriter.to_string(
        lambda writer: write_shape(writer, shape),
        filetype="s",
        fileversion=1
    )

    return shape_text


DEFAULT_LIST = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_count=True,
    newline_before_closing=True,
    newline_after_closing=True
)

SHAPE_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_start=True,
    newline_before_closing=True
)

VOL_SPHERE_BLOCK = BlockFormat(
    newline_after_start=True,
    newline_before_closing=True,
    newline_after_closing=True
)

PRIM_STATE_BLOCK = BlockFormat(
    newline_before_closing=True
)

TEX_IDXS_BLOCK = BlockFormat(
    newline_before_block=True
)

LIGHT_CFG_BLOCK = BlockFormat(
    newline_before_closing=True
)

UV_OPS_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_before_block=True,
    newline_after_count=True,
    newline_before_closing=True
)

LOD_CONTROL_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

DIST_LEVEL_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

DLEVEL_HEADER_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

SUB_OBJECT_BLOCK = BlockFormat(
    max_items_per_line=1,
    newline_after_start=True,
    newline_before_closing=True
)

SUBOBJ_HEADER_BLOCK = BlockFormat(
    newline_before_closing=True
)

GEOMETRY_INFO_BLOCK = BlockFormat(
    newline_before_block=True,
    newline_before_closing=True,
    newline_after_closing=True
)

GEOMETRY_NODE_BLOCK = BlockFormat(
    newline_before_closing=True
)

CULLABLE_PRIMS_BLOCK = BlockFormat(
    newline_before_block=True
)

SUBOBJ_SHADERS_BLOCK = BlockFormat(
    newline_after_closing=True
)

VERTEX_BLOCK = BlockFormat(
    newline_before_closing=True,
    newline_after_closing=True
)

VERTEX_UVS_BLOCK = BlockFormat(
    newline_before_block=True
)

INDEXED_TRILIST_BLOCK = BlockFormat(
    max_items_per_line=1,
    disable_inner_depth_increment=True,
    newline_after_start=True,
    newline_before_closing=True
)

VERTEX_IDXS_BLOCK = BlockFormat(
    max_items_per_line=197,
    max_items_first_line=186,
    allow_space_at_line_end=True
)

NORMAL_IDXS_BLOCK = BlockFormat(
    max_items_per_line=282,
    max_items_first_line=266,
    allow_space_at_line_end=True
)

FLAGS_BLOCK = BlockFormat(
    max_items_per_line=109,
    max_items_first_line=104,
    allow_space_at_line_end=True
)

ANIMATION_BLOCK = BlockFormat(
    newline_before_closing=True
)

ANIM_NODES_BLOCK = BlockFormat(
    newline_before_block=True,
    newline_before_closing=True
)


def write_shape(writer: BlockWriter, shape: Shape) -> None:
    """
    Write a shape block to a BlockWriter.

    Writes the `shape` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the shape block to.
        shape (Shape): The shape object to write.
    """
    with writer.sub_block(TokenID.shape, block_format=SHAPE_BLOCK) as shape_block:
        write_shape_header(shape_block, shape.shape_header)
        write_volumes(shape_block, shape.volumes)
        write_shader_names(shape_block, shape.shader_names)
        write_texture_filter_names(shape_block, shape.texture_filter_names)
        write_points(shape_block, shape.points)
        write_uv_points(shape_block, shape.uv_points)
        write_normals(shape_block, shape.normals)
        write_sort_vectors(shape_block, shape.sort_vectors)
        write_colours(shape_block, shape.colours)
        write_matrices(shape_block, shape.matrices)
        write_images(shape_block, shape.images)
        write_textures(shape_block, shape.textures)
        write_light_materials(shape_block, shape.light_materials)
        write_light_model_cfgs(shape_block, shape.light_model_cfgs)
        write_vtx_states(shape_block, shape.vtx_states)
        write_prim_states(shape_block, shape.prim_states)
        write_lod_controls(shape_block, shape.lod_controls)

        if shape.animations is not None:
            write_animations(shape_block, shape.animations)


def write_shape_header(writer: BlockWriter, header: ShapeHeader) -> None:
    """
    Write a shape header block to a BlockWriter.

    Writes the `shape_header` sub-block.

    Args:
        writer (BlockWriter): Writer to write the shape header block to.
        header (ShapeHeader): The shape header object to write.
    """
    if not isinstance(header, ShapeHeader):
        raise TypeError(f"Shape property 'shape_header' must be ShapeHeader, but got {type(header).__name__}")

    with writer.sub_block(TokenID.shape_header) as shape_header_block:
        shape_header_block.write_flags(header.flags1)

        if header.flags2 is not None:
            shape_header_block.write_flags(header.flags2)


def write_volumes(writer: BlockWriter, volumes: List[VolumeSphere]) -> None:
    """
    Write volume spheres to a BlockWriter.

    Writes the `volumes` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the volumes block to.
        volumes (List[VolumeSphere]): List of VolumeSphere objects to write.
    """
    for volume in volumes:
        if not isinstance(volume, VolumeSphere):
            raise TypeError(f"Shape property 'volumes' must contain VolumeSphere objects, but got {type(volume).__name__}")

    with writer.sub_block(TokenID.volumes, block_format=DEFAULT_LIST) as volumes_block:
        volumes_block.write_count(len(volumes))

        for volume in volumes:
            with volumes_block.sub_block(TokenID.vol_sphere, block_format=VOL_SPHERE_BLOCK) as vol_sphere_block:
                write_vector(vol_sphere_block, volume.vector)
                vol_sphere_block.write_float(volume.radius)


def write_vector(writer: BlockWriter, vector: Vector) -> None:
    """
    Write a 3D vector to a BlockWriter.

    Writes the `vector` sub-block.

    Args:
        writer (BlockWriter): Writer to write the vector block to.
        vector (Vector): The vector object to write.
    """
    if not isinstance(vector, Vector):
        raise TypeError(f"VolumeSphere property 'vector' must be Vector, but got {type(vector).__name__}")

    with writer.sub_block(TokenID.vector) as vector_block:
        vector_block.write_float(vector.x)
        vector_block.write_float(vector.y)
        vector_block.write_float(vector.z)


def write_shader_names(writer: BlockWriter, shader_names: List[str]) -> None:
    """
    Write shader names to a BlockWriter.

    Writes the `shader_names` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the shader names block to.
        shader_names (List[str]): List of shader name strings to write.
    """
    for shader_name in shader_names:
        if not isinstance(shader_name, str):
            raise TypeError(f"Shape property 'shader_names' must contain str values, but got {type(shader_name).__name__}")

    with writer.sub_block(TokenID.shader_names, block_format=DEFAULT_LIST) as shader_names_block:
        shader_names_block.write_count(len(shader_names))

        for shader_name in shader_names:
            with shader_names_block.sub_block(TokenID.named_shader) as named_shader_block:
                named_shader_block.write_string(shader_name)


def write_texture_filter_names(writer: BlockWriter, filter_names: List[str]) -> None:
    """
    Write texture filter names to a BlockWriter.

    Writes the `texture_filter_names` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the texture filter names block to.
        filter_names (List[str]): List of filter name strings to write.
    """
    for filter_name in filter_names:
        if not isinstance(filter_name, str):
            raise TypeError(f"Shape property 'texture_filter_names' must contain str values, but got {type(filter_name).__name__}")

    with writer.sub_block(TokenID.texture_filter_names, block_format=DEFAULT_LIST) as filter_names_block:
        filter_names_block.write_count(len(filter_names))

        for filter_name in filter_names:
            with filter_names_block.sub_block(TokenID.named_filter_mode) as named_filter_mode_block:
                named_filter_mode_block.write_string(filter_name)


def write_points(writer: BlockWriter, points: List[Point]) -> None:
    """
    Write 3D points to a BlockWriter.

    Writes the `points` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the points block to.
        points (List[Point]): List of Point objects to write.
    """
    for point in points:
        if not isinstance(point, Point):
            raise TypeError(f"Shape property 'points' must contain Point objects, but got {type(point).__name__}")

    with writer.sub_block(TokenID.points, block_format=DEFAULT_LIST) as points_block:
        points_block.write_count(len(points))

        for point in points:
            with points_block.sub_block(TokenID.point) as point_block:
                point_block.write_float(point.x)
                point_block.write_float(point.y)
                point_block.write_float(point.z)


def write_uv_points(writer: BlockWriter, uv_points: List[UVPoint]) -> None:
    """
    Write UV points to a BlockWriter.

    Writes the `uv_points` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the UV points block to.
        uv_points (List[UVPoint]): List of UV point objects to write.
    """
    for uv_point in uv_points:
        if not isinstance(uv_point, UVPoint):
            raise TypeError(f"Shape property 'uv_points' must contain UVPoint objects, but got {type(uv_point).__name__}")

    with writer.sub_block(TokenID.uv_points, block_format=DEFAULT_LIST) as uv_points_block:
        uv_points_block.write_count(len(uv_points))

        for uv_point in uv_points:
            with uv_points_block.sub_block(TokenID.uv_point) as uv_point_block:
                uv_point_block.write_float(uv_point.u)
                uv_point_block.write_float(uv_point.v)


def write_normals(writer: BlockWriter, normals: List[Vector]) -> None:
    """
    Write normals to a BlockWriter.

    Writes the `normals` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the normals block to.
        normals (List[Vector]): List of normal vectors to write.
    """
    for normal in normals:
        if not isinstance(normal, Vector):
            raise TypeError(f"Shape property 'normals' must contain Vector objects, but got {type(normal).__name__}")

    with writer.sub_block(TokenID.normals, block_format=DEFAULT_LIST) as normals_block:
        normals_block.write_count(len(normals))

        for normal in normals:
            write_vector(normals_block, normal)


def write_sort_vectors(writer: BlockWriter, sort_vectors: List[Vector]) -> None:
    """
    Write sort vectors to a BlockWriter.

    Writes the `sort_vectors` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the sort vectors block to.
        sort_vectors (List[Vector]): List of sort vectors to write.
    """
    for sort_vector in sort_vectors:
        if not isinstance(sort_vector, Vector):
            raise TypeError(f"Shape property 'sort_vectors' must contain Vector objects, but got {type(sort_vector).__name__}")

    with writer.sub_block(TokenID.sort_vectors, block_format=DEFAULT_LIST) as sort_vectors_block:
        sort_vectors_block.write_count(len(sort_vectors))

        for sort_vector in sort_vectors:
            write_vector(sort_vectors_block, sort_vector)


def write_colours(writer: BlockWriter, colours: List[Colour]) -> None:
    """
    Write colours to a BlockWriter.

    Writes the `colours` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the colours block to.
        colours (List[Colour]): List of colour objects to write.
    """
    for colour in colours:
        if not isinstance(colour, Colour):
            raise TypeError(f"Shape property 'colours' must contain Colour objects, but got {type(colour).__name__}")

    with writer.sub_block(TokenID.colours, block_format=DEFAULT_LIST) as colours_block:
        colours_block.write_count(len(colours))
        
        for colour in colours:
            with colours_block.sub_block(TokenID.colour) as colour_block:
                colour_block.write_float(colour.a)
                colour_block.write_float(colour.r)
                colour_block.write_float(colour.g)
                colour_block.write_float(colour.b)


def write_matrices(writer: BlockWriter, matrices: List[Matrix]) -> None:
    """
    Write matrices to a BlockWriter.

    Writes the `matrices` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the matrices block to.
        matrices (List[Matrix]): List of matrix objects to write.
    """
    for matrix in matrices:
        if not isinstance(matrix, Matrix):
            raise TypeError(f"Shape property 'matrices' must contain Matrix objects, but got {type(matrix).__name__}")

    with writer.sub_block(TokenID.matrices, block_format=DEFAULT_LIST) as matrices_block:
        matrices_block.write_count(len(matrices))

        for matrix in matrices:
            with matrices_block.sub_block(TokenID.matrix, block_label=matrix.name) as matrix_block:
                matrix_block.write_float(matrix.ax)
                matrix_block.write_float(matrix.ay)
                matrix_block.write_float(matrix.az)
                matrix_block.write_float(matrix.bx)
                matrix_block.write_float(matrix.by)
                matrix_block.write_float(matrix.bz)
                matrix_block.write_float(matrix.cx)
                matrix_block.write_float(matrix.cy)
                matrix_block.write_float(matrix.cz)
                matrix_block.write_float(matrix.dx)
                matrix_block.write_float(matrix.dy)
                matrix_block.write_float(matrix.dz)


def write_images(writer: BlockWriter, images: List[str]) -> None:
    """
    Write images to a BlockWriter.

    Writes the `images` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the images block to.
        images (List[str]): List of image name strings to write.
    """
    for image in images:
        if not isinstance(image, str):
            raise TypeError(f"Shape property 'images' must contain str values, but got {type(image).__name__}")

    with writer.sub_block(TokenID.images, block_format=DEFAULT_LIST) as images_block:
        images_block.write_count(len(images))

        for image in images:
            with images_block.sub_block(TokenID.image) as image_block:
                image_block.write_string(image)


def write_textures(writer: BlockWriter, textures: List[Texture]) -> None:
    """
    Write textures to a BlockWriter.

    Writes the `textures` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the textures block to.
        textures (List[Texture]): List of texture objects to write.
    """
    for texture in textures:
        if not isinstance(texture, Texture):
            raise TypeError(f"Shape property 'textures' must contain Texture objects, but got {type(texture).__name__}")

    with writer.sub_block(TokenID.textures, block_format=DEFAULT_LIST) as textures_block:
        textures_block.write_count(len(textures))

        for texture in textures:
            with textures_block.sub_block(TokenID.texture) as texture_block:
                texture_block.write_int(texture.image_index)
                texture_block.write_int(texture.filter_mode)
                texture_block.write_float(texture.mipmap_lod_bias)

                if texture.border_colour is not None:
                    texture_block.write_flags(texture.border_colour)


def write_light_materials(writer: BlockWriter, light_materials: List[LightMaterial]) -> None:
    """
    Write light materials to a BlockWriter.

    Writes the `light_materials` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the light materials block to.
        light_materials (List[LightMaterial]): List of light material objects to write.
    """
    for light_material in light_materials:
        if not isinstance(light_material, LightMaterial):
            raise TypeError(f"Shape property 'light_materials' must contain LightMaterial objects, but got {type(light_material).__name__}")

    with writer.sub_block(TokenID.light_materials, block_format=DEFAULT_LIST) as light_materials_block:
        light_materials_block.write_count(len(light_materials))

        for light_material in light_materials:
            with light_materials_block.sub_block(TokenID.light_material) as light_material_block:
                light_material_block.write_flags(light_material.flags)
                light_material_block.write_int(light_material.diff_colour_index)
                light_material_block.write_int(light_material.amb_colour_index)
                light_material_block.write_int(light_material.spec_colour_index)
                light_material_block.write_int(light_material.emissive_colour_index)
                light_material_block.write_float(light_material.spec_power)


def write_light_model_cfgs(writer: BlockWriter, light_model_cfgs: List[LightModelCfg]) -> None:
    """
    Write light model configurations to a BlockWriter.

    Writes the `light_model_cfgs` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the light model configurations block to.
        light_model_cfgs (List[LightModelCfg]): List of light model configuration objects to write.
    """
    for light_model_cfg in light_model_cfgs:
        if not isinstance(light_model_cfg, LightModelCfg):
            raise TypeError(f"Shape property 'light_model_cfgs' must contain LightModelCfg objects, but got {type(light_model_cfg).__name__}")

    with writer.sub_block(TokenID.light_model_cfgs, block_format=DEFAULT_LIST) as light_model_cfgs_block:
        light_model_cfgs_block.write_count(len(light_model_cfgs))

        for light_model_cfg in light_model_cfgs:
            with light_model_cfgs_block.sub_block(TokenID.light_model_cfg, block_format=LIGHT_CFG_BLOCK) as light_model_cfg_block:
                light_model_cfg_block.write_flags(light_model_cfg.flags)
                write_uv_ops(light_model_cfg_block, light_model_cfg.uv_ops)


def write_uv_ops(writer: BlockWriter, uv_ops: List[UVOp]) -> None:
    """
    Write UV operations to a BlockWriter.

    Writes the `uv_ops` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the UV operations block to.
        uv_ops (List[UVOp]): List of UV operation objects to write.
    """
    for uv_op in uv_ops:
        if not isinstance(uv_op, UVOp):
            raise TypeError(f"LightModelCfg property 'uv_ops' must contain UVOp objects, but got {type(uv_op).__name__}")

    with writer.sub_block(TokenID.uv_ops, block_format=UV_OPS_BLOCK) as uv_ops_block:
        uv_ops_block.write_count(len(uv_ops))

        for uv_op in uv_ops:
            if isinstance(uv_op, UVOpCopy):
                with uv_ops_block.sub_block(TokenID.uv_op_copy) as uv_op_block:
                    uv_op_block.write_int(uv_op.texture_address_mode)
                    uv_op_block.write_int(uv_op.source_uv_index)
            
            elif isinstance(uv_op, UVOpReflectMapFull):
                with uv_ops_block.sub_block(TokenID.uv_op_reflectmapfull) as uv_op_block:
                    uv_op_block.write_int(uv_op.texture_address_mode)
            
            elif isinstance(uv_op, UVOpReflectMap):
                with uv_ops_block.sub_block(TokenID.uv_op_reflectmap) as uv_op_block:
                    uv_op_block.write_int(uv_op.texture_address_mode)
            
            elif isinstance(uv_op, UVOpUniformScale):
                with uv_ops_block.sub_block(TokenID.uv_op_uniformscale) as uv_op_block:
                    uv_op_block.write_int(uv_op.texture_address_mode)
                    uv_op_block.write_int(uv_op.source_uv_index)
                    uv_op_block.write_int(uv_op.unknown3)
                    uv_op_block.write_int(uv_op.unknown4)
            
            elif isinstance(uv_op, UVOpNonUniformScale):
                with uv_ops_block.sub_block(TokenID.uv_op_nonuniformscale) as uv_op_block:
                    uv_op_block.write_int(uv_op.texture_address_mode)
                    uv_op_block.write_int(uv_op.source_uv_index)
                    uv_op_block.write_int(uv_op.unknown3)
                    uv_op_block.write_int(uv_op.unknown4)


def write_vtx_states(writer: BlockWriter, vtx_states: List[VtxState]) -> None:
    """
    Write vertex states to a BlockWriter.

    Writes the `vtx_states` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the vertex states block to.
        vtx_states (List[VtxState]): List of vertex state objects to write.
    """
    for vtx_state in vtx_states:
        if not isinstance(vtx_state, VtxState):
            raise TypeError(f"Shape property 'vtx_states' must contain VtxState objects, but got {type(vtx_state).__name__}")

    with writer.sub_block(TokenID.vtx_states, block_format=DEFAULT_LIST) as vtx_states_block:
        vtx_states_block.write_count(len(vtx_states))

        for vtx_state in vtx_states:
            with vtx_states_block.sub_block(TokenID.vtx_state) as vtx_state_block:
                vtx_state_block.write_flags(vtx_state.flags)
                vtx_state_block.write_int(vtx_state.matrix_index)
                vtx_state_block.write_int(vtx_state.light_material_index)
                vtx_state_block.write_int(vtx_state.light_model_cfg_index)
                vtx_state_block.write_flags(vtx_state.light_flags)

                if vtx_state.matrix2_index is not None:
                    vtx_state_block.write_int(vtx_state.matrix2_index)


def write_prim_states(writer: BlockWriter, prim_states: List[PrimState]) -> None:
    """
    Write primitive states to a BlockWriter.

    Writes the `prim_states` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the primitive states block to.
        prim_states (List[PrimState]): List of primitive state objects to write.
    """
    for prim_state in prim_states:
        if not isinstance(prim_state, PrimState):
            raise TypeError(f"Shape property 'prim_states' must contain PrimState objects, but got {type(prim_state).__name__}")

    with writer.sub_block(TokenID.prim_states, block_format=DEFAULT_LIST) as prim_states_block:
        prim_states_block.write_count(len(prim_states))

        for prim_state in prim_states:
            with prim_states_block.sub_block(TokenID.prim_state, block_label=prim_state.name, block_format=PRIM_STATE_BLOCK) as prim_state_block:
                prim_state_block.write_flags(prim_state.flags)
                prim_state_block.write_int(prim_state.shader_index)
                write_tex_idxs(prim_state_block, prim_state.texture_indices)
                prim_state_block.write_float(prim_state.z_bias)
                prim_state_block.write_int(prim_state.vtx_state_index)
                prim_state_block.write_int(prim_state.alpha_test_mode)
                prim_state_block.write_int(prim_state.light_cfg_index)
                prim_state_block.write_int(prim_state.z_buffer_mode)


def write_tex_idxs(writer: BlockWriter, tex_idxs: List[int]) -> None:
    """
    Write texture indices to a BlockWriter.

    Writes the `tex_idxs` sub-block.

    Args:
        writer (BlockWriter): Writer to write the texture indices block to.
        tex_idxs (List[int]): List of texture index integers to write.
    """
    for tex_idx in tex_idxs:
        if not isinstance(tex_idx, int):
            raise TypeError(f"PrimState property 'texture_indices' must contain int values, but got {type(tex_idx).__name__}")

    with writer.sub_block(TokenID.tex_idxs, block_format=TEX_IDXS_BLOCK) as tex_idxs_block:
        tex_idxs_block.write_count(len(tex_idxs))

        for tex_idx in tex_idxs:
            tex_idxs_block.write_int(tex_idx)


def write_lod_controls(writer: BlockWriter, lod_controls: List[LodControl]) -> None:
    """
    Write LOD controls to a BlockWriter.

    Writes the `lod_controls` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the LOD controls block to.
        lod_controls (List[LodControl]): List of LOD control objects to write.
    """
    for lod_control in lod_controls:
        if not isinstance(lod_control, LodControl):
            raise TypeError(f"Shape property 'lod_controls' must contain LodControl objects, but got {type(lod_control).__name__}")

    with writer.sub_block(TokenID.lod_controls, block_format=DEFAULT_LIST) as lod_control_block:
        lod_control_block.write_count(len(lod_controls))

        for lod_control in lod_controls:
            with lod_control_block.sub_block(TokenID.lod_control, block_format=LOD_CONTROL_BLOCK) as lod_control_block:
                with lod_control_block.sub_block(TokenID.distance_levels_header) as dist_level_header_block:
                    dist_level_header_block.write_int(lod_control.distance_levels_header)
                
                write_distance_levels(lod_control_block, lod_control.distance_levels)


def write_distance_levels(writer: BlockWriter, distance_levels: List[DistanceLevel]) -> None:
    """
    Write distance levels to a BlockWriter.

    Writes the `distance_levels` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the distance levels block to.
        distance_levels (List[DistanceLevel]): List of distance level objects to write.
    """
    for distance_level in distance_levels:
        if not isinstance(distance_level, DistanceLevel):
            raise TypeError(f"LodControl property 'distance_levels' must contain DistanceLevel objects, but got {type(distance_level).__name__}")

    with writer.sub_block(TokenID.distance_levels, block_format=DEFAULT_LIST) as distance_levels_block:
        distance_levels_block.write_count(len(distance_levels))

        for distance_level in distance_levels:
            with distance_levels_block.sub_block(TokenID.distance_level, block_format=DIST_LEVEL_BLOCK) as distance_level_block:
                write_distance_level_header(distance_level_block, distance_level.distance_level_header)
                write_sub_objects(distance_level_block, distance_level.sub_objects)


def write_distance_level_header(writer: BlockWriter, header: DistanceLevelHeader) -> None:
    """
    Write a distance level header to a BlockWriter.

    Writes the `distance_level_header` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the distance level header block to.
        header (DistanceLevelHeader): The distance level header object to write.
    """
    if not isinstance(header, DistanceLevelHeader):
        raise TypeError(f"DistanceLevel property 'distance_level_header' must be DistanceLevelHeader, but got {type(header).__name__}")

    with writer.sub_block(TokenID.distance_level_header, block_format=DLEVEL_HEADER_BLOCK) as dist_level_header_block:
        with dist_level_header_block.sub_block(TokenID.dlevel_selection) as dlevel_selection_block:
            dlevel_selection_block.write_int(int(header.dlevel_selection))
        
        with dist_level_header_block.sub_block(TokenID.hierarchy) as hierarchy_block:
            hierarchy_block.write_count(len(header.hierarchy))

            for value in header.hierarchy:
                hierarchy_block.write_int(value)


def write_sub_objects(writer: BlockWriter, sub_objects: List[SubObject]) -> None:
    """
    Write sub-objects to a BlockWriter.

    Writes the `sub_objects` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the sub-objects block to.
        sub_objects (List[SubObject]): List of sub-object objects to write.
    """
    for sub_object in sub_objects:
        if not isinstance(sub_object, SubObject):
            raise TypeError(f"DistanceLevel property 'sub_objects' must contain SubObject objects, but got {type(sub_object).__name__}")

    with writer.sub_block(TokenID.sub_objects, block_format=DEFAULT_LIST) as sub_objects_block:
        sub_objects_block.write_count(len(sub_objects))

        for sub_object in sub_objects:
            with sub_objects_block.sub_block(TokenID.sub_object, block_format=SUB_OBJECT_BLOCK) as sub_object_block:
                write_sub_object_header(sub_object_block, sub_object.sub_object_header)
                write_vertices(sub_object_block, sub_object.vertices)
                write_vertex_sets(sub_object_block, sub_object.vertex_sets)
                write_primitives(sub_object_block, sub_object.primitives)


def write_sub_object_header(writer: BlockWriter, header: SubObjectHeader) -> None:
    """
    Write a sub-object header to a BlockWriter.

    Writes the `sub_object_header` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the sub-object header block to.
        header (SubObjectHeader): The sub-object header object to write.
    """
    if not isinstance(header, SubObjectHeader):
        raise TypeError(f"SubObject property 'sub_object_header' must be SubObjectHeader, but got {type(header).__name__}")

    with writer.sub_block(TokenID.sub_object_header, block_format=SUBOBJ_HEADER_BLOCK) as sub_object_header_block:
        sub_object_header_block.write_flags(header.flags)
        sub_object_header_block.write_int(header.sort_vector_index)
        sub_object_header_block.write_int(header.volume_index)
        sub_object_header_block.write_flags(header.source_vtx_fmt_flags)
        sub_object_header_block.write_flags(header.destination_vtx_fmt_flags)
        write_geometry_info(sub_object_header_block, header.geometry_info)
        write_subobject_shaders(sub_object_header_block, header.subobject_shaders)
        write_subobject_light_cfgs(sub_object_header_block, header.subobject_light_cfgs)
        sub_object_header_block.write_int(header.subobject_id)


def write_geometry_info(writer: BlockWriter, geometry_info: GeometryInfo) -> None:
    """
    Write geometry info to a BlockWriter.

    Writes the `geometry_info` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the geometry info block to.
        info (GeometryInfo): The geometry info object to write.
    """
    if not isinstance(geometry_info, GeometryInfo):
        raise TypeError(f"SubObjectHeader property 'geometry_info' must be GeometryInfo, but got {type(geometry_info).__name__}")

    with writer.sub_block(TokenID.geometry_info, block_format=GEOMETRY_INFO_BLOCK) as geometry_info_block:
        geometry_info_block.write_int(geometry_info.face_normals)
        geometry_info_block.write_int(geometry_info.tx_light_cmds)
        geometry_info_block.write_int(geometry_info.node_x_tx_light_cmds)
        geometry_info_block.write_int(geometry_info.trilist_indices)
        geometry_info_block.write_int(geometry_info.line_list_indices)
        geometry_info_block.write_int(geometry_info.node_x_trilist_indices)
        geometry_info_block.write_int(geometry_info.trilists)
        geometry_info_block.write_int(geometry_info.line_lists)
        geometry_info_block.write_int(geometry_info.pt_lists)
        geometry_info_block.write_int(geometry_info.node_x_trilists)
        write_geometry_nodes(geometry_info_block, geometry_info.geometry_nodes)
        write_geometry_node_map(geometry_info_block, geometry_info.geometry_node_map)


def write_geometry_nodes(writer: BlockWriter, geometry_nodes: List[GeometryNode]) -> None:
    """
    Write geometry nodes to a BlockWriter.

    Writes the `geometry_nodes` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the geometry nodes block to.
        geometry_nodes (List[GeometryNode]): List of geometry node objects to write.
    """
    for geometry_node in geometry_nodes:
        if not isinstance(geometry_node, GeometryNode):
            raise TypeError(f"GeometryInfo property 'geometry_nodes' must contain GeometryNode objects, but got {type(geometry_node).__name__}")

    with writer.sub_block(TokenID.geometry_nodes, block_format=DEFAULT_LIST) as geometry_nodes_block:
        geometry_nodes_block.write_count(len(geometry_nodes))

        for geometry_node in geometry_nodes:
            with geometry_nodes_block.sub_block(TokenID.geometry_node, block_format=GEOMETRY_NODE_BLOCK) as geometry_node_block:
                geometry_node_block.write_int(geometry_node.tx_light_cmds)
                geometry_node_block.write_int(geometry_node.node_x_tx_light_cmds)
                geometry_node_block.write_int(geometry_node.trilists)
                geometry_node_block.write_int(geometry_node.line_lists)
                geometry_node_block.write_int(geometry_node.pt_lists)
                write_cullable_prims(geometry_node_block, geometry_node.cullable_prims)


def write_cullable_prims(writer: BlockWriter, cullable_prims: CullablePrims) -> None:
    """
    Write cullable primitives to a BlockWriter.

    Writes the `cullable_prims` sub-block.

    Args:
        writer (BlockWriter): Writer to write the cullable primitives block to.
        cullable_prims (CullablePrims): The cullable primitives object to write.
    """
    if not isinstance(cullable_prims, CullablePrims):
        raise TypeError(f"GeometryNode property 'cullable_prims' must be CullablePrims, but got {type(cullable_prims).__name__}")

    with writer.sub_block(TokenID.cullable_prims, block_format=CULLABLE_PRIMS_BLOCK) as cullable_prims_block:
        cullable_prims_block.write_int(cullable_prims.num_prims)
        cullable_prims_block.write_int(cullable_prims.num_flat_sections)
        cullable_prims_block.write_int(cullable_prims.num_prim_indices)


def write_geometry_node_map(writer: BlockWriter, geometry_node_map: List[int]) -> None:
    """
    Write a geometry node map to a BlockWriter.

    Writes the `geometry_node_map` sub-block.

    Args:
        writer (BlockWriter): Writer to write the geometry node map block to.
        geometry_node_map (List[int]): List of geometry node map integers to write.
    """
    for value in geometry_node_map:
        if not isinstance(value, int):
            raise TypeError(f"GeometryInfo property 'geometry_node_map' must contain int values, but got {type(value).__name__}")

    with writer.sub_block(TokenID.geometry_node_map) as geometry_node_map_block:
        geometry_node_map_block.write_count(len(geometry_node_map))

        for value in geometry_node_map:
            geometry_node_map_block.write_int(value)


def write_subobject_shaders(writer: BlockWriter, shaders: List[int]) -> None:
    """
    Write sub-object shaders to a BlockWriter.

    Writes the `subobject_shaders` sub-block.

    Args:
        writer (BlockWriter): Writer to write the sub-object shaders block to.
        shaders (List[int]): List of shader index integers to write.
    """
    for shader in shaders:
        if not isinstance(shader, int):
            raise TypeError(f"SubObjectHeader property 'subobject_shaders' must contain int values, but got {type(shader).__name__}")

    with writer.sub_block(TokenID.subobject_shaders, block_format=SUBOBJ_SHADERS_BLOCK) as subobject_shaders_block:
        subobject_shaders_block.write_count(len(shaders))

        for shader in shaders:
            subobject_shaders_block.write_int(shader)


def write_subobject_light_cfgs(writer: BlockWriter, light_cfgs: List[int]) -> None:
    """
    Write sub-object light configurations to a BlockWriter.

    Writes the `subobject_light_cfgs` sub-block.

    Args:
        writer (BlockWriter): Writer to write the sub-object light configurations block to.
        light_cfgs (List[int]): List of light configuration index integers to write.
    """
    for light_cfg in light_cfgs:
        if not isinstance(light_cfg, int):
            raise TypeError(f"SubObjectHeader property 'subobject_light_cfgs' must contain int values, but got {type(light_cfg).__name__}")

    with writer.sub_block(TokenID.subobject_light_cfgs) as subobject_light_cfgs_block:
        subobject_light_cfgs_block.write_count(len(light_cfgs))

        for light_cfg in light_cfgs:
            subobject_light_cfgs_block.write_int(light_cfg)


def write_vertices(writer: BlockWriter, vertices: List[Vertex]) -> None:
    """
    Write vertices to a BlockWriter.

    Writes the `vertices` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the vertices block to.
        vertices (List[Vertex]): List of vertex objects to write.
    """
    for vertex in vertices:
        if not isinstance(vertex, Vertex):
            raise TypeError(f"SubObject property 'vertices' must contain Vertex objects, but got {type(vertex).__name__}")

    with writer.sub_block(TokenID.vertices, block_format=DEFAULT_LIST) as vertices_block:
        vertices_block.write_count(len(vertices))

        for vertex in vertices:
            with vertices_block.sub_block(TokenID.vertex, block_format=VERTEX_BLOCK) as vertex_block:
                vertex_block.write_flags(vertex.flags)
                vertex_block.write_int(vertex.point_index)
                vertex_block.write_int(vertex.normal_index)
                vertex_block.write_flags(vertex.colour1)
                vertex_block.write_flags(vertex.colour2)
                write_vertex_uvs(vertex_block, vertex.vertex_uvs)


def write_vertex_uvs(writer: BlockWriter, vertex_uvs: List[int]) -> None:
    """
    Write vertex UVs to a BlockWriter.

    Writes the `vertex_uvs` sub-block.

    Args:
        writer (BlockWriter): Writer to write the vertex UVs block to.
        vertex_uvs (List[int]): List of vertex UV index integers to write.
    """
    for vertex_uv in vertex_uvs:
        if not isinstance(vertex_uv, int):
            raise TypeError(f"Vertex property 'vertex_uvs' must contain int values, but got {type(vertex_uv).__name__}")

    with writer.sub_block(TokenID.vertex_uvs, block_format=VERTEX_UVS_BLOCK) as vertex_uvs_block:
        vertex_uvs_block.write_count(len(vertex_uvs))

        for vertex_uv in vertex_uvs:
            vertex_uvs_block.write_int(vertex_uv)


def write_vertex_sets(writer: BlockWriter, vertex_sets: List[VertexSet]) -> None:
    """
    Write vertex sets to a BlockWriter.

    Writes the `vertex_sets` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the vertex sets block to.
        vertex_sets (List[VertexSet]): List of vertex set objects to write.
    """
    for vertex_set in vertex_sets:
        if not isinstance(vertex_set, VertexSet):
            raise TypeError(f"SubObject property 'vertex_sets' must contain VertexSet objects, but got {type(vertex_set).__name__}")

    with writer.sub_block(TokenID.vertex_sets, block_format=DEFAULT_LIST) as vertex_sets_block:
        vertex_sets_block.write_count(len(vertex_sets))

        for vertex_set in vertex_sets:
            with vertex_sets_block.sub_block(TokenID.vertex_set) as vertex_set_block:
                vertex_set_block.write_int(vertex_set.vtx_state)
                vertex_set_block.write_int(vertex_set.vtx_start_index)
                vertex_set_block.write_int(vertex_set.vtx_count)


def write_primitives(writer: BlockWriter, primitives: List[Primitive]) -> None:
    """
    Write primitives to a BlockWriter.

    Writes the `primitives` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the primitives block to.
        primitives (List[Primitive]): List of primitive objects to write.
    """
    for primitive in primitives:
        if not isinstance(primitive, Primitive):
            raise TypeError(f"SubObject property 'primitives' must contain Primitive objects, but got {type(primitive).__name__}")

    primitives_list_count = 0
    last_prim_state_index = -1

    for primitive in primitives:
        if primitive.prim_state_index != last_prim_state_index:
            primitives_list_count += 1
            last_prim_state_index = primitive.prim_state_index
        
        primitives_list_count += 1

    with writer.sub_block(TokenID.primitives, block_format=DEFAULT_LIST) as primitives_block:
        primitives_block.write_count(primitives_list_count)

        last_prim_state_index = -1

        for primitive in primitives:
            if primitive.prim_state_index != last_prim_state_index:
                with primitives_block.sub_block(TokenID.prim_state_idx) as prim_state_idx_block:
                    prim_state_idx_block.write_int(primitive.prim_state_index)
                last_prim_state_index = primitive.prim_state_index
            
            with primitives_block.sub_block(TokenID.indexed_trilist, block_format=INDEXED_TRILIST_BLOCK) as indexed_trilist_block:
                write_vertex_idxs(indexed_trilist_block, primitive.indexed_trilist.vertex_idxs)
                write_normal_idxs(indexed_trilist_block, primitive.indexed_trilist.normal_idxs)
                write_flags(indexed_trilist_block, primitive.indexed_trilist.flags)


def write_vertex_idxs(writer: BlockWriter, vertex_idxs: List[VertexIdx]) -> None:
    """
    Write vertex indices to a BlockWriter.

    Writes the `vertex_idxs` sub-block.

    Args:
        writer (BlockWriter): Writer to write the vertex indices block to.
        vertex_idxs (List[VertexIdx]): List of vertex index objects to write.
    """
    for vertex_idx in vertex_idxs:
        if not isinstance(vertex_idx, VertexIdx):
            raise TypeError(f"IndexedTrilist property 'vertex_idxs' must contain VertexIdx objects, but got {type(vertex_idx).__name__}")

    with writer.sub_block(TokenID.vertex_idxs, block_format=VERTEX_IDXS_BLOCK) as vertex_idxs_block:
        vertex_idxs_block.write_count(len(vertex_idxs) * 3)

        for vertex_idx in vertex_idxs:
            vertex_idxs_block.write_int(vertex_idx.vertex1_index)
            vertex_idxs_block.write_int(vertex_idx.vertex2_index)
            vertex_idxs_block.write_int(vertex_idx.vertex3_index)


def write_normal_idxs(writer: BlockWriter, normal_idxs: List[NormalIdx]) -> None:
    """
    Write normal indices to a BlockWriter.

    Writes the `normal_idxs` sub-block.

    Args:
        writer (BlockWriter): Writer to write the normal indices block to.
        normal_idxs (List[NormalIdx]): List of normal index objects to write.
    """
    for normal_idx in normal_idxs:
        if not isinstance(normal_idx, NormalIdx):
            raise TypeError(f"IndexedTrilist property 'normal_idxs' must contain NormalIdx objects, but got {type(normal_idx).__name__}")

    with writer.sub_block(TokenID.normal_idxs, block_format=NORMAL_IDXS_BLOCK) as normal_idxs_block:
        normal_idxs_block.write_count(len(normal_idxs))

        for normal_idx in normal_idxs:
            normal_idxs_block.write_int(normal_idx.index)
            normal_idxs_block.write_int(normal_idx.unknown2)


def write_flags(writer: BlockWriter, flags: List[int]) -> None:
    """
    Write flags to a BlockWriter.

    Writes the `flags` sub-block.

    Args:
        writer (BlockWriter): Writer to write the flags block to.
        flags (List[int]): List of flag values to write.
    """
    for flag in flags:
        if not isinstance(flag, int):
            raise TypeError(f"IndexedTrilist property 'flags' must contain int values, but got {type(flag).__name__}")

    with writer.sub_block(TokenID.flags, block_format=FLAGS_BLOCK) as flags_block:
        flags_block.write_count(len(flags))

        for flag in flags:
            flags_block.write_flags(flag)


def write_animations(writer: BlockWriter, animations: List[Animation]) -> None:
    """
    Write animations to a BlockWriter.

    Writes the `animations` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the animations block to.
        animations (List[Animation]): List of animation objects to write.
    """
    for animation in animations:
        if not isinstance(animation, Animation):
            raise TypeError(f"Shape property 'animations' must contain Animation objects, but got {type(animation).__name__}")

    with writer.sub_block(TokenID.animations, block_format=DEFAULT_LIST) as animations_block:
        animations_block.write_count(len(animations))

        for animation in animations:
            with animations_block.sub_block(TokenID.animation, block_format=ANIMATION_BLOCK) as animation_block:
                animation_block.write_int(animation.frame_count)
                animation_block.write_int(animation.frame_rate)
                write_anim_nodes(animation_block, animation.animation_nodes)


def write_anim_nodes(writer: BlockWriter, anim_nodes: List[AnimationNode]) -> None:
    """
    Write animation nodes to a BlockWriter.

    Writes the `anim_nodes` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the animation nodes block to.
        anim_nodes (List[AnimationNode]): List of animation node objects to write.
    """
    for anim_node in anim_nodes:
        if not isinstance(anim_node, AnimationNode):
            raise TypeError(f"Animation property 'animation_nodes' must contain AnimationNode objects, but got {type(anim_node).__name__}")

    with writer.sub_block(TokenID.anim_nodes, block_format=ANIM_NODES_BLOCK) as anim_nodes_block:
        anim_nodes_block.write_count(len(anim_nodes))

        for anim_node in anim_nodes:
            with anim_nodes_block.sub_block(TokenID.anim_node, block_label=anim_node.name, block_format=DEFAULT_LIST) as anim_node_block:
                write_controllers(anim_node_block, anim_node.controllers)


def write_controllers(writer: BlockWriter, controllers: List[Controller]) -> None:
    """
    Write controllers to a BlockWriter.

    Writes the `controllers` sub-block and its child blocks.

    Args:
        writer (BlockWriter): Writer to write the controllers block to.
        controllers (List[Controller]): List of controller objects to write.
    """
    for controller in controllers:
        if not isinstance(controller, Controller):
            raise TypeError(f"AnimationNode property 'controllers' must contain Controller objects, but got {type(controller).__name__}")

    with writer.sub_block(TokenID.controllers, block_format=DEFAULT_LIST) as controllers_block:
        controllers_block.write_count(len(controllers))

        for controller in controllers:
            if isinstance(controller, TCBRot):
                with controllers_block.sub_block(TokenID.tcb_rot, block_format=DEFAULT_LIST) as tcb_rot_block:
                    write_keypositions(tcb_rot_block, controller.keyframes)
            
            elif isinstance(controller, LinearPos):
                with controllers_block.sub_block(TokenID.linear_pos, block_format=DEFAULT_LIST) as linear_pos_block:
                    write_keypositions(linear_pos_block, controller.keyframes)
            
            elif isinstance(controller, TCBPos):
                with controllers_block.sub_block(TokenID.tcb_pos, block_format=DEFAULT_LIST) as tcb_pos_block:
                    write_keypositions(tcb_pos_block, controller.keyframes)


def write_keypositions(writer: BlockWriter, keypositions: List[KeyPosition]) -> None:
    """
    Write key positions to a BlockWriter.

    Writes key position blocks.

    Args:
        writer (BlockWriter): Writer to write the key positions to.
        keypositions (List[KeyPosition]): List of key position objects to write.
    """
    for keyposition in keypositions:
        if not isinstance(keyposition, KeyPosition):
            raise TypeError(f"Controller property 'keyframes' must contain KeyPosition objects, but got {type(keyposition).__name__}")

    writer.write_count(len(keypositions))
    
    for keyposition in keypositions:
        if isinstance(keyposition, TCBKey):
            with writer.sub_block(TokenID.tcb_key) as tcb_key_block:
                tcb_key_block.write_int(keyposition.frame)
                tcb_key_block.write_float(keyposition.x)
                tcb_key_block.write_float(keyposition.y)
                tcb_key_block.write_float(keyposition.z)
                tcb_key_block.write_float(keyposition.w)
                tcb_key_block.write_float(keyposition.tension)
                tcb_key_block.write_float(keyposition.continuity)
                tcb_key_block.write_float(keyposition.bias)
                tcb_key_block.write_float(keyposition.ease_in)
                tcb_key_block.write_float(keyposition.ease_out)
        
        elif isinstance(keyposition, LinearKey):
            with writer.sub_block(TokenID.linear_key) as linear_key_block:
                linear_key_block.write_int(keyposition.frame)
                linear_key_block.write_float(keyposition.x)
                linear_key_block.write_float(keyposition.y)
                linear_key_block.write_float(keyposition.z)
        
        elif isinstance(keyposition, SlerpRot):
            with writer.sub_block(TokenID.slerp_rot) as slerp_rot_block:
                slerp_rot_block.write_int(keyposition.frame)
                slerp_rot_block.write_float(keyposition.x)
                slerp_rot_block.write_float(keyposition.y)
                slerp_rot_block.write_float(keyposition.z)
                slerp_rot_block.write_float(keyposition.w)