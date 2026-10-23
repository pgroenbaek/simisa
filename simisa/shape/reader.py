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
) -> Shape:
    """
    Load and parse a shape file from disk.

    This function supports both compressed/uncompressed as well as binary/text data.
    It opens the file at the given path, validates that it is a supported shape
    file based on its subheader, and returns a parsed Shape object.

    Args:
        filepath (str): Path to the shape file.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        Shape: The parsed shape object.

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

        if not reader.filetype == 's':
            raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a shape file?")

        return read_shape(reader)


def loads(
    shape_text: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> Shape:
    """
    Parse a shape from a string containing shape data.

    This function does not support binary or compressed data. It reads shape
    data from the provided string, validates that it represents a supported
    shape file based on its subheader, and returns a parsed Shape object.

    Args:
        shape_text (str): String containing shape file data.
        progress (ProgressCallback, optional): Callback for receiving progress updates.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        Shape: The parsed shape object.

    Raises:
        TypeError: If a parameter is not of the expected type.
        SimisaHeaderError: If the data has an invalid or unrecognized SIMISA header.
        SimisaSubheaderError: If the data has an invalid or unrecognized SIMISA subheader.
        BlockReaderError: If the block reader encounters an error or malformed data.
        StfReaderError: If the STF reader encounters an error or malformed data.
        UnresolvableIncludeError: If includes within the file cannot be resolved.
    """
    if not isinstance(shape_text, str):
        raise TypeError(f"Parameter 'shape_text' must be str, but got {type(shape_text).__name__}")

    reader = BlockReader.from_string(shape_text, progress=progress, verbose=verbose)

    if not reader.filetype == 's':
        raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a shape file?")

    return read_shape(reader)


def read_shape(reader: BlockReader) -> Shape:
    """
    Read and parse a shape block from a BlockReader.

    Consumes the `shape` sub-block and its child blocks, returning a fully
    constructed Shape object.

    Args:
        reader (BlockReader): Reader positioned at a shape block.

    Returns:
        Shape: The parsed shape.
    """
    reader.report_progress("Reading shape data...")

    with reader.sub_block(TokenID.shape) as shape_block:
        shape_header = read_shape_header(shape_block)
        volumes = read_volumes(shape_block)
        shader_names = read_shader_names(shape_block)
        texture_filter_names = read_texture_filter_names(shape_block)
        points = read_points(shape_block)
        uv_points = read_uv_points(shape_block)
        normals = read_normals(shape_block)
        sort_vectors = read_sort_vectors(shape_block)
        colours = read_colours(shape_block)
        matrices = read_matrices(shape_block)
        images = read_images(shape_block)
        textures = read_textures(shape_block)
        light_materials = read_light_materials(shape_block)
        light_model_cfgs = read_light_model_cfgs(shape_block)
        vtx_states = read_vtx_states(shape_block)
        prim_states = read_prim_states(shape_block)
        lod_controls = read_lod_controls(shape_block)

        if not shape_block.end_of_block():
            animations = read_animations(shape_block)
        else:
            animations = None

        return Shape(
            shape_header=shape_header,
            volumes=volumes,
            shader_names=shader_names,
            texture_filter_names=texture_filter_names,
            points=points,
            uv_points=uv_points,
            normals=normals,
            sort_vectors=sort_vectors,
            colours=colours,
            matrices=matrices,
            images=images,
            textures=textures,
            light_materials=light_materials,
            light_model_cfgs=light_model_cfgs,
            vtx_states=vtx_states,
            prim_states=prim_states,
            lod_controls=lod_controls,
            animations=animations
        )


def read_shape_header(reader: BlockReader) -> ShapeHeader:
    """
    Read and parse a shape header block from a BlockReader.

    Consumes the `shape_header` sub-block, returning a fully
    constructed ShapeHeader object.

    Args:
        reader (BlockReader): Reader positioned at a shape header block.

    Returns:
        ShapeHeader: The parsed shape header.
    """
    with reader.sub_block(TokenID.shape_header) as header_block:
        flags1 = header_block.read_flags()
        flags2 = None

        if not header_block.end_of_block():
            flags2 = header_block.read_flags()

        return ShapeHeader(
            flags1=flags1,
            flags2=flags2
        )


def read_volumes(reader: BlockReader) -> List[VolumeSphere]:
    """
    Read and parse volume spheres from a BlockReader.

    Consumes the `volumes` sub-block and returns a list of VolumeSphere objects.

    Args:
        reader (BlockReader): Reader positioned at a volumes block.

    Returns:
        List[VolumeSphere]: The parsed volume spheres.
    """
    with reader.sub_block(TokenID.volumes) as volumes_block:
        volume_spheres: List[VolumeSphere] = []
        count = volumes_block.read_int()
        
        for vol_sphere_block in volumes_block:
            reader.report_progress("Reading volumes...")

            vol_sphere_block.verify_id(TokenID.vol_sphere)

            vector = read_vector(vol_sphere_block)
            radius = vol_sphere_block.read_float()

            volume_spheres.append(VolumeSphere(
                vector=vector,
                radius=radius
            ))

        volumes_block.verify_count(count, len(volume_spheres))

        return volume_spheres


def read_vector(reader: BlockReader) -> Vector:
    """
    Read and parse a 3D vector from a BlockReader.

    Consumes the `vector` sub-block and returns a Vector object.

    Args:
        reader (BlockReader): Reader positioned at a vector block.

    Returns:
        Vector: The parsed vector.
    """
    with reader.sub_block(TokenID.vector) as vector_block:
        x = vector_block.read_float()
        y = vector_block.read_float()
        z = vector_block.read_float()

        return Vector(
            x=x,
            y=y,
            z=z
        )


def read_shader_names(reader: BlockReader) -> List[str]:
    """
    Read and parse shader names from a BlockReader.

    Consumes the `shader_names` sub-block and returns a list of strings.

    Args:
        reader (BlockReader): Reader positioned at a shader names block.

    Returns:
        List[str]: The parsed shader names.
    """
    with reader.sub_block(TokenID.shader_names) as shader_names_block:
        shader_names: List[str] = []
        count = shader_names_block.read_int()
        
        for named_shader_block in shader_names_block:
            named_shader_block.verify_id(TokenID.named_shader)

            named_shader = named_shader_block.read_string()
            shader_names.append(named_shader)

        shader_names_block.verify_count(count, len(shader_names))

        return shader_names


def read_texture_filter_names(reader: BlockReader) -> List[str]:
    """
    Read and parse texture filter names from a BlockReader.

    Consumes the `texture_filter_names` sub-block and returns a list of strings.

    Args:
        reader (BlockReader): Reader positioned at a texture filter names block.

    Returns:
        List[str]: The parsed texture filter names.
    """
    with reader.sub_block(TokenID.texture_filter_names) as texture_filter_names_block:
        named_filter_modes: List[str] = []
        count = texture_filter_names_block.read_int()
        
        for named_filter_mode_block in texture_filter_names_block:
            named_filter_mode_block.verify_id(TokenID.named_filter_mode)

            named_filter_mode = named_filter_mode_block.read_string()
            named_filter_modes.append(named_filter_mode)

        texture_filter_names_block.verify_count(count, len(named_filter_modes))

        return named_filter_modes


def read_points(reader: BlockReader) -> List[Point]:
    """
    Read and parse 3D points from a BlockReader.

    Consumes the `points` sub-block and returns a list of Point objects.

    Args:
        reader (BlockReader): Reader positioned at a points block.

    Returns:
        List[Point]: The parsed points.
    """
    with reader.sub_block(TokenID.points) as points_block:
        points: List[Point] = []
        count = points_block.read_int()
        
        for point_block in points_block:
            reader.report_progress("Reading points...")

            point_block.verify_id(TokenID.point)

            x = point_block.read_float()
            y = point_block.read_float()
            z = point_block.read_float()

            points.append(Point(
                x=x,
                y=y,
                z=z
            ))

        points_block.verify_count(count, len(points))

        return points


def read_uv_points(reader: BlockReader) -> List[UVPoint]:
    """
    Read and parse UV points from a BlockReader.

    Consumes the `uv_points` sub-block and returns a list of UVPoint objects.

    Args:
        reader (BlockReader): Reader positioned at a UV points block.

    Returns:
        List[UVPoint]: The parsed UV points.
    """
    with reader.sub_block(TokenID.uv_points) as uv_points_block:
        uv_points: List[UVPoint] = []
        count = uv_points_block.read_int()
        
        for uv_point_block in uv_points_block:
            reader.report_progress("Reading UV points...")

            uv_point_block.verify_id(TokenID.uv_point)

            u = uv_point_block.read_float()
            v = uv_point_block.read_float()

            uv_points.append(UVPoint(
                u=u,
                v=v
            ))

        uv_points_block.verify_count(count, len(uv_points))

        return uv_points


def read_normals(reader: BlockReader) -> List[Vector]:
    """
    Read and parse normal vectors from a BlockReader.

    Consumes the `normals` sub-block and returns a list of Vector objects.

    Args:
        reader (BlockReader): Reader positioned at a normals block.

    Returns:
        List[Vector]: The parsed normals.
    """
    with reader.sub_block(TokenID.normals) as normals_block:
        normals: List[Vector] = []
        count = normals_block.read_int()
        
        for vector_block in normals_block:
            reader.report_progress("Reading normals...")

            vector_block.verify_id(TokenID.vector)

            x = vector_block.read_float()
            y = vector_block.read_float()
            z = vector_block.read_float()

            normals.append(Vector(
                x=x,
                y=y,
                z=z
            ))

        normals_block.verify_count(count, len(normals))

        return normals


def read_sort_vectors(reader: BlockReader) -> List[Vector]:
    """
    Read and parse sort vectors from a BlockReader.

    Consumes the `sort_vectors` sub-block and returns a list of Vector objects.

    Args:
        reader (BlockReader): Reader positioned at a sort vectors block.

    Returns:
        List[Vector]: The parsed sort vectors.
    """
    with reader.sub_block(TokenID.sort_vectors) as sort_vectors_block:
        sort_vectors: List[Vector] = []
        count = sort_vectors_block.read_int()
        
        for vector_block in sort_vectors_block:
            vector_block.verify_id(TokenID.vector)

            x = vector_block.read_float()
            y = vector_block.read_float()
            z = vector_block.read_float()

            sort_vectors.append(Vector(
                x=x,
                y=y,
                z=z
            ))

        sort_vectors_block.verify_count(count, len(sort_vectors))

        return sort_vectors


def read_colours(reader: BlockReader) -> List[Colour]:
    """
    Read and parse colours from a BlockReader.

    Consumes the `colours` sub-block and returns a list of Colour objects.

    Args:
        reader (BlockReader): Reader positioned at a colours block.

    Returns:
        List[Colour]: The parsed colours.
    """
    with reader.sub_block(TokenID.colours) as colours_block:
        colours: List[Colour] = []
        count = colours_block.read_int()
        
        for colour_block in colours_block:
            colour_block.verify_id(TokenID.colour)

            a = colour_block.read_float()
            r = colour_block.read_float()
            g = colour_block.read_float()
            b = colour_block.read_float()

            colours.append(Colour(
                a=a,
                r=r,
                g=g,
                b=b
            ))

        colours_block.verify_count(count, len(colours))

        return colours


def read_matrices(reader: BlockReader) -> List[Matrix]:
    """
    Read and parse transformation matrices from a BlockReader.

    Consumes the `matrices` sub-block and returns a list of Matrix objects.

    Args:
        reader (BlockReader): Reader positioned at a matrices block.

    Returns:
        List[Matrix]: The parsed matrices.
    """
    with reader.sub_block(TokenID.matrices) as matrices_block:
        matrices: List[Matrix] = []
        count = matrices_block.read_int()
        
        for matrix_block in matrices_block:
            reader.report_progress("Reading matrices...")

            matrix_block.verify_id(TokenID.matrix)

            name = matrix_block.label
            ax = matrix_block.read_float()
            ay = matrix_block.read_float()
            az = matrix_block.read_float()
            bx = matrix_block.read_float()
            by = matrix_block.read_float()
            bz = matrix_block.read_float()
            cx = matrix_block.read_float()
            cy = matrix_block.read_float()
            cz = matrix_block.read_float()
            dx = matrix_block.read_float()
            dy = matrix_block.read_float()
            dz = matrix_block.read_float()

            matrix = Matrix(
                name=name,
                ax=ax,
                ay=ay,
                az=az,
                bx=bx,
                by=by,
                bz=bz,
                cx=cx,
                cy=cy,
                cz=cz,
                dx=dx,
                dy=dy,
                dz=dz
            )
            matrices.append(matrix)

        matrices_block.verify_count(count, len(matrices))

        return matrices


def read_images(reader: BlockReader) -> List[str]:
    """
    Read and parse image names from a BlockReader.

    Consumes the `images` sub-block and returns a list of strings.

    Args:
        reader (BlockReader): Reader positioned at an images block.

    Returns:
        List[str]: The parsed image names.
    """
    with reader.sub_block(TokenID.images) as images_block:
        images: List[str] = []
        count = images_block.read_int()
        
        for image_block in images_block:
            image_block.verify_id(TokenID.image)

            image = image_block.read_string()
            images.append(image)

        images_block.verify_count(count, len(images))

        return images


def read_textures(reader: BlockReader) -> List[Texture]:
    """
    Read and parse textures from a BlockReader.

    Consumes the `textures` sub-block and returns a list of Texture objects.

    Args:
        reader (BlockReader): Reader positioned at a textures block.

    Returns:
        List[Texture]: The parsed textures.
    """
    with reader.sub_block(TokenID.textures) as textures_block:
        textures: List[Texture] = []
        count = textures_block.read_int()
        
        for texture_block in textures_block:
            reader.report_progress("Reading textures...")

            texture_block.verify_id(TokenID.texture)

            image_index = texture_block.read_int()
            filter_mode = texture_block.read_int()
            mipmap_lod_bias = texture_block.read_float()
            border_colour = None
            
            if not texture_block.end_of_block():
                border_colour = texture_block.read_flags()
            
            texture = Texture(
                image_index=image_index,
                filter_mode=filter_mode,
                mipmap_lod_bias=mipmap_lod_bias,
                border_colour=border_colour
            )
            textures.append(texture)

        textures_block.verify_count(count, len(textures))

        return textures


def read_light_materials(reader: BlockReader) -> List[LightMaterial]:
    """
    Read and parse light materials from a BlockReader.

    Consumes the `light_materials` sub-block and returns a list of LightMaterial objects.

    Args:
        reader (BlockReader): Reader positioned at a light materials block.

    Returns:
        List[LightMaterial]: The parsed light materials.
    """
    with reader.sub_block(TokenID.light_materials) as light_materials_block:
        light_materials: List[LightMaterial] = []
        count = light_materials_block.read_int()

        for light_material_block in light_materials_block:
            light_material_block.verify_id(TokenID.light_material)

            flags = light_material_block.read_flags()
            diff_colour_index = light_material_block.read_int()
            amb_colour_index = light_material_block.read_int()
            spec_colour_index = light_material_block.read_int()
            emissive_colour_index = light_material_block.read_int()
            spec_power = light_material_block.read_float()

            light_material = LightMaterial(
                flags=flags,
                diff_colour_index=diff_colour_index,
                amb_colour_index=amb_colour_index,
                spec_colour_index=spec_colour_index,
                emissive_colour_index=emissive_colour_index,
                spec_power=spec_power
            )
            light_materials.append(light_material)

        light_materials_block.verify_count(count, len(light_materials))

        return light_materials


def read_light_model_cfgs(reader: BlockReader) -> List[LightModelCfg]:
    """
    Read and parse light model configurations from a BlockReader.

    Consumes the `light_model_cfgs` sub-block and returns a list of LightModelCfg objects.

    Args:
        reader (BlockReader): Reader positioned at a light model configs block.

    Returns:
        List[LightModelCfg]: The parsed light model configurations.
    """
    with reader.sub_block(TokenID.light_model_cfgs) as light_model_cfgs_block:
        light_model_cfgs: List[LightMaterial] = []
        count = light_model_cfgs_block.read_int()

        for light_model_cfg_block in light_model_cfgs_block:
            light_model_cfg_block.verify_id(TokenID.light_model_cfg)

            flags = light_model_cfg_block.read_flags()
            uv_ops = read_uv_ops(light_model_cfg_block)

            light_model_cfgs.append(LightModelCfg(
                flags=flags,
                uv_ops=uv_ops
            ))

        light_model_cfgs_block.verify_count(count, len(light_model_cfgs))

        return light_model_cfgs


def read_uv_ops(reader: BlockReader) -> List[UVOp]:
    """
    Read and parse UV operations from a BlockReader.

    Consumes the `uv_ops` sub-block and returns a list of UVOp objects.

    Args:
        reader (BlockReader): Reader positioned at a UV ops block.

    Returns:
        List[UVOp]: The parsed UV operations.
    """
    with reader.sub_block(TokenID.uv_ops) as uv_ops_block:
        count = uv_ops_block.read_int()
        uv_ops: List[UVOp] = []

        for uv_op_block in uv_ops_block:
            if uv_op_block.id == TokenID.uv_op_copy:
                texture_address_mode = uv_op_block.read_int()
                source_uv_index = uv_op_block.read_int()

                uv_ops.append(UVOpCopy(
                    texture_address_mode=texture_address_mode,
                    source_uv_index=source_uv_index
                ))

            elif uv_op_block.id == TokenID.uv_op_reflectmapfull:
                texture_address_mode = uv_op_block.read_int()

                uv_ops.append(UVOpReflectMapFull(
                    texture_address_mode=texture_address_mode
                ))

            elif uv_op_block.id == TokenID.uv_op_reflectmap:
                texture_address_mode = uv_op_block.read_int()

                uv_ops.append(UVOpReflectMap(
                    texture_address_mode=texture_address_mode
                ))

            elif uv_op_block.id == TokenID.uv_op_uniformscale:
                texture_address_mode = uv_op_block.read_int()
                source_uv_index = uv_op_block.read_int()
                unknown3 = uv_op_block.read_int()
                unknown4 = uv_op_block.read_int()

                uv_ops.append(UVOpUniformScale(
                    texture_address_mode=texture_address_mode,
                    source_uv_index=source_uv_index,
                    unknown3=unknown3,
                    unknown4=unknown4
                ))

            elif uv_op_block.id == TokenID.uv_op_nonuniformscale:
                texture_address_mode = uv_op_block.read_int()
                source_uv_index = uv_op_block.read_int()
                unknown3 = uv_op_block.read_int()
                unknown4 = uv_op_block.read_int()

                uv_ops.append(UVOpNonUniformScale(
                    texture_address_mode=texture_address_mode,
                    source_uv_index=source_uv_index,
                    unknown3=unknown3,
                    unknown4=unknown4
                ))

            else:
                logger.warning(f"Unhandled uv_op: {uv_op_block.id.name} (id: {uv_op_block.id})")
                uv_op_block.skip()
        
        uv_ops_block.verify_count(count, len(uv_ops))

        return uv_ops


def read_vtx_states(reader: BlockReader) -> List[VtxState]:
    """
    Read and parse vertex states from a BlockReader.

    Consumes the `vtx_states` sub-block and returns a list of VtxState objects.

    Args:
        reader (BlockReader): Reader positioned at a vertex states block.

    Returns:
        List[VtxState]: The parsed vertex states.
    """
    with reader.sub_block(TokenID.vtx_states) as vtx_states_block:
        vtx_states: List[VtxState] = []
        count = vtx_states_block.read_int()
        
        for vtx_state_block in vtx_states_block:
            reader.report_progress("Reading vtx states...")

            vtx_state_block.verify_id(TokenID.vtx_state)

            flags = vtx_state_block.read_flags()
            matrix_index = vtx_state_block.read_int()
            light_material_index = vtx_state_block.read_int()
            light_model_cfg_index = vtx_state_block.read_int()
            light_flags = vtx_state_block.read_flags()
            matrix2_index = None
            
            if not vtx_state_block.end_of_block():
                matrix2_index = vtx_state_block.read_int()
            
            vtx_state = VtxState(
                flags=flags,
                matrix_index=matrix_index,
                light_material_index=light_material_index,
                light_model_cfg_index=light_model_cfg_index,
                light_flags=light_flags,
                matrix2_index=matrix2_index
            )
            vtx_states.append(vtx_state)

        vtx_states_block.verify_count(count, len(vtx_states))

        return vtx_states


def read_prim_states(reader: BlockReader) -> List[PrimState]:
    """
    Read and parse primitive states from a BlockReader.

    Consumes the `prim_states` sub-block and returns a list of PrimState objects.

    Args:
        reader (BlockReader): Reader positioned at a primitive states block.

    Returns:
        List[PrimState]: The parsed primitive states.
    """
    with reader.sub_block(TokenID.prim_states) as prim_states_block:
        prim_states: List[VtxState] = []
        count = prim_states_block.read_int()
        
        for prim_state_block in prim_states_block:
            reader.report_progress("Reading prim states...")

            prim_state_block.verify_id(TokenID.prim_state)

            name = prim_state_block.label
            flags = prim_state_block.read_flags()
            shader_index = prim_state_block.read_int()
            texture_indices = read_tex_idxs(prim_state_block)
            z_bias = prim_state_block.read_float()
            vtx_state_index = prim_state_block.read_int()
            alpha_test_mode = prim_state_block.read_int()
            light_cfg_index = prim_state_block.read_int()
            z_buffer_mode = prim_state_block.read_int()
            
            prim_state = PrimState(
                name=name,
                flags=flags,
                shader_index=shader_index,
                texture_indices=texture_indices,
                z_bias=z_bias,
                vtx_state_index=vtx_state_index,
                alpha_test_mode=alpha_test_mode,
                light_cfg_index=light_cfg_index,
                z_buffer_mode=z_buffer_mode
            )
            prim_states.append(prim_state)

        prim_states_block.verify_count(count, len(prim_states))

        return prim_states


def read_tex_idxs(reader: BlockReader) -> List[int]:
    """
    Read and parse texture index lists from a BlockReader.

    Consumes the `tex_idxs` sub-block and returns a list of integer texture indices.

    Args:
        reader (BlockReader): Reader positioned at a texture indices block.

    Returns:
        List[int]: The parsed texture indices.
    """
    with reader.sub_block(TokenID.tex_idxs) as tex_idxs_block:
        tex_idxs: List[int] = []
        count = tex_idxs_block.read_int()
        
        for _ in range(count):
            tex_idxs.append(tex_idxs_block.read_int())

        tex_idxs_block.verify_count(count, len(tex_idxs))

        return tex_idxs


def read_lod_controls(reader: BlockReader) -> List[LodControl]:
    """
    Read and parse LOD controls from a BlockReader.

    Consumes the `lod_controls` sub-block and returns a list of LodControl objects.

    Args:
        reader (BlockReader): Reader positioned at a LOD controls block.

    Returns:
        List[LodControl]: The parsed LOD controls.
    """
    with reader.sub_block(TokenID.lod_controls) as lod_controls_block:
        lod_controls: List[LodControl] = []
        count = lod_controls_block.read_int()
        
        for lod_control_block in lod_controls_block:
            lod_control_block.verify_id(TokenID.lod_control)

            distance_levels_header: int = 0
            distance_levels: List[DistanceLevel] = []

            with lod_control_block.sub_block(TokenID.distance_levels_header) as dlevels_header_block:
                distance_levels_header = dlevels_header_block.read_int()
            
            distance_levels = read_distance_levels(lod_control_block)

            lod_control = LodControl(
                distance_levels_header=distance_levels_header,
                distance_levels=distance_levels
            )
            lod_controls.append(lod_control)

        lod_controls_block.verify_count(count, len(lod_controls))

        return lod_controls


def read_distance_levels(reader: BlockReader) -> List[DistanceLevel]:
    """
    Read and parse distance levels from a BlockReader.

    Consumes the `distance_levels` sub-block and returns a list of DistanceLevel objects.

    Args:
        reader (BlockReader): Reader positioned at a distance levels block.

    Returns:
        List[DistanceLevel]: The parsed distance levels.
    """
    with reader.sub_block(TokenID.distance_levels) as distance_levels_block:
        distance_levels: List[DistanceLevel] = []
        count = distance_levels_block.read_int()
        
        for distance_level_block in distance_levels_block:
            distance_level_block.verify_id(TokenID.distance_level)

            distance_level_header = read_distance_level_header(distance_level_block)
            sub_objects = read_sub_objects(distance_level_block)

            distance_level = DistanceLevel(
                distance_level_header=distance_level_header,
                sub_objects=sub_objects
            )
            distance_levels.append(distance_level)

        distance_levels_block.verify_count(count, len(distance_levels))

        return distance_levels


def read_distance_level_header(reader: BlockReader) -> DistanceLevelHeader:
    """
    Read and parse a distance level header from a BlockReader.

    Consumes the `distance_level_header` sub-block and returns a DistanceLevelHeader object.

    Args:
        reader (BlockReader): Reader positioned at a distance level header block.

    Returns:
        DistanceLevelHeader: The parsed distance level header.
    """
    with reader.sub_block(TokenID.distance_level_header) as dlevel_header_block:
        dlevel_selection: int = 0
        hierarchy: List[int] = []
        
        with dlevel_header_block.sub_block(TokenID.dlevel_selection) as dlevel_selection_block:
            dlevel_selection = int(dlevel_selection_block.read_float())
        
        with dlevel_header_block.sub_block(TokenID.hierarchy) as hierarchy_block:
            count = hierarchy_block.read_int()
            
            for _ in range(count):
                hierarchy.append(hierarchy_block.read_int())

            hierarchy_block.verify_count(count, len(hierarchy))

        return DistanceLevelHeader(
            dlevel_selection=dlevel_selection,
            hierarchy=hierarchy
        )


def read_sub_objects(reader: BlockReader) -> List[SubObject]:
    """
    Read and parse sub-objects from a BlockReader.

    Consumes the `sub_objects` sub-block and returns a list of SubObject objects.

    Args:
        reader (BlockReader): Reader positioned at a sub-objects block.

    Returns:
        List[SubObject]: The parsed sub-objects.
    """
    with reader.sub_block(TokenID.sub_objects) as sub_objects_block:
        sub_objects: List[SubObject] = []
        count = sub_objects_block.read_int()
        
        for idx, sub_object_block in enumerate(sub_objects_block):
            sub_object_block.verify_id(TokenID.sub_object)

            sub_object_header = read_sub_object_header(sub_object_block)
            vertices = read_vertices(sub_object_block)
            vertex_sets = read_vertex_sets(sub_object_block)
            primitives = read_primitives(sub_object_block)

            sub_object = SubObject(
                sub_object_header=sub_object_header,
                vertices=vertices,
                vertex_sets=vertex_sets,
                primitives=primitives
            )
            sub_objects.append(sub_object)

        sub_objects_block.verify_count(count, len(sub_objects))

        return sub_objects


def read_sub_object_header(reader: BlockReader) -> List[SubObjectHeader]:
    """
    Read and parse a sub-object header from a BlockReader.

    Consumes the `sub_object_header` sub-block and returns a SubObjectHeader object.

    Args:
        reader (BlockReader): Reader positioned at a sub-object header block.

    Returns:
        SubObjectHeader: The parsed sub-object header.
    """
    with reader.sub_block(TokenID.sub_object_header) as sub_object_header_block:
        flags = sub_object_header_block.read_flags()
        sort_vector_index = sub_object_header_block.read_int()
        volume_index = sub_object_header_block.read_int()
        source_vtx_fmt_flags = sub_object_header_block.read_flags()
        destination_vtx_fmt_flags = sub_object_header_block.read_flags()
        geometry_info = read_geometry_info(sub_object_header_block)
        subobject_shaders = read_subobject_shaders(sub_object_header_block)
        subobject_light_cfgs = read_subobject_light_cfgs(sub_object_header_block)
        subobject_id = sub_object_header_block.read_int()

        sub_object_header = SubObjectHeader(
            flags=flags,
            sort_vector_index=sort_vector_index,
            volume_index=volume_index,
            source_vtx_fmt_flags=source_vtx_fmt_flags,
            destination_vtx_fmt_flags=destination_vtx_fmt_flags,
            geometry_info=geometry_info,
            subobject_shaders=subobject_shaders,
            subobject_light_cfgs=subobject_light_cfgs,
            subobject_id=subobject_id
        )
        return sub_object_header


def read_geometry_info(reader: BlockReader) -> GeometryInfo:
    """
    Read and parse geometry information from a BlockReader.

    Consumes the `geometry_info` sub-block and returns a GeometryInfo object.

    Args:
        reader (BlockReader): Reader positioned at a geometry info block.

    Returns:
        GeometryInfo: The parsed geometry information.
    """
    reader.report_progress("Reading geometry info...")

    with reader.sub_block(TokenID.geometry_info) as geometry_info_block:
        face_normals = geometry_info_block.read_int()
        tx_light_cmds = geometry_info_block.read_int()
        node_x_tx_light_cmds = geometry_info_block.read_int()
        trilist_indices = geometry_info_block.read_int()
        line_list_indices = geometry_info_block.read_int()
        node_x_trilist_indices = geometry_info_block.read_int()
        trilists = geometry_info_block.read_int()
        line_lists = geometry_info_block.read_int()
        pt_lists = geometry_info_block.read_int()
        node_x_trilists = geometry_info_block.read_int()
        geometry_nodes = read_geometry_nodes(geometry_info_block)
        geometry_node_map = read_geometry_node_map(geometry_info_block)

        geometry_info = GeometryInfo(
            face_normals=face_normals,
            tx_light_cmds=tx_light_cmds,
            node_x_tx_light_cmds=node_x_tx_light_cmds,
            trilist_indices=trilist_indices,
            line_list_indices=line_list_indices,
            node_x_trilist_indices=node_x_trilist_indices,
            trilists=trilists,
            line_lists=line_lists,
            pt_lists=pt_lists,
            node_x_trilists=node_x_trilists,
            geometry_nodes=geometry_nodes,
            geometry_node_map=geometry_node_map
        )
        return geometry_info


def read_geometry_nodes(reader: BlockReader) -> List[GeometryNode]:
    """
    Read and parse geometry nodes from a BlockReader.

    Consumes the `geometry_nodes` sub-block and returns a list of GeometryNode objects.

    Args:
        reader (BlockReader): Reader positioned at a geometry nodes block.

    Returns:
        List[GeometryNode]: The parsed geometry nodes.
    """
    with reader.sub_block(TokenID.geometry_nodes) as geometry_nodes_block:
        geometry_nodes: List[GeometryNode] = []
        count = geometry_nodes_block.read_int()
        
        for geometry_node_block in geometry_nodes_block:
            geometry_node_block.verify_id(TokenID.geometry_node)

            tx_light_cmds = geometry_node_block.read_int()
            node_x_tx_light_cmds = geometry_node_block.read_int()
            trilists = geometry_node_block.read_int()
            line_lists = geometry_node_block.read_int()
            pt_lists = geometry_node_block.read_int()
            cullable_prims = read_cullable_prims(geometry_node_block)

            geometry_node = GeometryNode(
                tx_light_cmds=tx_light_cmds,
                node_x_tx_light_cmds=node_x_tx_light_cmds,
                trilists=trilists,
                line_lists=line_lists,
                pt_lists=pt_lists,
                cullable_prims=cullable_prims
            )
            geometry_nodes.append(geometry_node)

        geometry_nodes_block.verify_count(count, len(geometry_nodes))

        return geometry_nodes


def read_cullable_prims(reader: BlockReader) -> CullablePrims:
    """
    Read and parse cullable primitives from a BlockReader.

    Consumes the `cullable_prims` sub-block and returns a CullablePrims object.

    Args:
        reader (BlockReader): Reader positioned at a cullable prims block.

    Returns:
        CullablePrims: The parsed cullable primitives.
    """
    with reader.sub_block(TokenID.cullable_prims) as cullable_prims_block:
        num_prims = cullable_prims_block.read_int()
        num_flat_sections = cullable_prims_block.read_int()
        num_prim_indices = cullable_prims_block.read_int()

        return CullablePrims(
            num_prims=num_prims,
            num_flat_sections=num_flat_sections,
            num_prim_indices=num_prim_indices
        )


def read_geometry_node_map(reader: BlockReader) -> List[int]:
    """
    Read and parse a geometry node map from a BlockReader.

    Consumes the `geometry_node_map` sub-block and returns a list of indices.

    Args:
        reader (BlockReader): Reader positioned at a geometry node map block.

    Returns:
        List[int]: The parsed geometry node map.
    """
    with reader.sub_block(TokenID.geometry_node_map) as geometry_node_map_block:
        geometry_node_map: List[int] = []
        count = geometry_node_map_block.read_int()
        
        for _ in range(count):
            geometry_node_map.append(geometry_node_map_block.read_int())

        geometry_node_map_block.verify_count(count, len(geometry_node_map))

        return geometry_node_map


def read_subobject_shaders(reader: BlockReader) -> List[int]:
    """
    Read and parse sub-object shader indices from a BlockReader.

    Consumes the `subobject_shaders` sub-block and returns a list of indices.

    Args:
        reader (BlockReader): Reader positioned at a subobject shaders block.

    Returns:
        List[int]: The parsed shader indices.
    """
    with reader.sub_block(TokenID.subobject_shaders) as subobject_shaders_block:
        subobject_shaders: List[int] = []
        count = subobject_shaders_block.read_int()
        
        for _ in range(count):
            subobject_shaders.append(subobject_shaders_block.read_int())

        subobject_shaders_block.verify_count(count, len(subobject_shaders))

        return subobject_shaders


def read_subobject_light_cfgs(reader: BlockReader) -> List[int]:
    """
    Read and parse sub-object light configuration indices from a BlockReader.

    Consumes the `subobject_light_cfgs` sub-block and returns a list of indices.

    Args:
        reader (BlockReader): Reader positioned at a subobject light configs block.

    Returns:
        List[int]: The parsed light configuration indices.
    """
    with reader.sub_block(TokenID.subobject_light_cfgs) as subobject_light_cfgs_block:
        subobject_light_cfgs: List[int] = []
        count = subobject_light_cfgs_block.read_int()
        
        for _ in range(count):
            subobject_light_cfgs.append(subobject_light_cfgs_block.read_int())

        subobject_light_cfgs_block.verify_count(count, len(subobject_light_cfgs))

        return subobject_light_cfgs


def read_vertices(reader: BlockReader) -> List[Vertex]:
    """
    Read and parse vertices from a BlockReader.

    Consumes the `vertices` sub-block and returns a list of Vertex objects.

    Args:
        reader (BlockReader): Reader positioned at a vertices block.

    Returns:
        List[Vertex]: The parsed vertices.
    """
    with reader.sub_block(TokenID.vertices) as vertices_block:
        vertices: List[Vertex] = []
        count = vertices_block.read_int()
        
        for vertex_block in vertices_block:
            reader.report_progress("Reading vertices...")

            vertex_block.verify_id(TokenID.vertex)

            flags = vertex_block.read_flags()
            point_index = vertex_block.read_int()
            normal_index = vertex_block.read_int()
            colour1 = vertex_block.read_flags()
            colour2 = vertex_block.read_flags()
            vertex_uvs = read_vertex_uvs(vertex_block)

            vertex = Vertex(
                flags=flags,
                point_index=point_index,
                normal_index=normal_index,
                colour1=colour1,
                colour2=colour2,
                vertex_uvs=vertex_uvs
            )
            vertices.append(vertex)

        vertices_block.verify_count(count, len(vertices))

        return vertices


def read_vertex_uvs(reader: BlockReader) -> List[int]:
    """
    Read and parse vertex UV indices from a BlockReader.

    Consumes the `vertex_uvs` sub-block and returns a list of indices.

    Args:
        reader (BlockReader): Reader positioned at a vertex UVs block.

    Returns:
        List[int]: The parsed vertex UV indices.
    """
    with reader.sub_block(TokenID.vertex_uvs) as vertex_uvs_block:
        vertex_uvs: List[int] = []
        count = vertex_uvs_block.read_int()
        
        for _ in range(count):
            vertex_uvs.append(vertex_uvs_block.read_int())

        vertex_uvs_block.verify_count(count, len(vertex_uvs))

        return vertex_uvs


def read_vertex_sets(reader: BlockReader) -> List[VertexSet]:
    """
    Read and parse vertex sets from a BlockReader.

    Consumes the `vertex_sets` sub-block and returns a list of VertexSet objects.

    Args:
        reader (BlockReader): Reader positioned at a vertex sets block.

    Returns:
        List[VertexSet]: The parsed vertex sets.
    """
    with reader.sub_block(TokenID.vertex_sets) as vertex_sets_block:
        vertex_sets: List[VertexSet] = []
        count = vertex_sets_block.read_int()
        
        for vertex_set_block in vertex_sets_block:
            vertex_set_block.verify_id(TokenID.vertex_set)

            vtx_state = vertex_set_block.read_int()
            vtx_start_index = vertex_set_block.read_int()
            vtx_count = vertex_set_block.read_int()

            vertex_set = VertexSet(
                vtx_state=vtx_state,
                vtx_start_index=vtx_start_index,
                vtx_count=vtx_count
            )
            vertex_sets.append(vertex_set)

        vertex_sets_block.verify_count(count, len(vertex_sets))

        return vertex_sets


def read_primitives(reader: BlockReader) -> List[Primitive]:
    """
    Read and parse primitives from a BlockReader.

    Consumes the `primitives` sub-block and returns a list of Primitive objects.

    Args:
        reader (BlockReader): Reader positioned at a primitives block.

    Returns:
        List[Primitive]: The parsed primitives.
    """
    with reader.sub_block(TokenID.primitives) as primitives_block:
        primitives: List[Primitive] = []
        count = primitives_block.read_int()
        
        num_blocks_read = 0
        prim_state_index = 0
        
        for primitive_block in primitives_block:
            if primitive_block.id == TokenID.prim_state_idx:
                prim_state_index = primitive_block.read_int()
        
            elif primitive_block.id == TokenID.indexed_trilist:
                vertex_idxs = read_vertex_idxs(primitive_block)
                normal_idxs = read_normal_idxs(primitive_block)
                flags = read_flags(primitive_block)

                indexed_trilist = IndexedTrilist(
                    vertex_idxs=vertex_idxs,
                    normal_idxs=normal_idxs,
                    flags=flags
                )
                primitive = Primitive(
                    prim_state_index=prim_state_index,
                    indexed_trilist=indexed_trilist
                )

                primitives.append(primitive)
            
            else:
                logger.warning(f"Unhandled primitive: {primitive_block.id.name} (id: {primitive_block.id})")
                primitive_block.skip()

            num_blocks_read += 1

        primitives_block.verify_count(count, num_blocks_read)

        return primitives


def read_vertex_idxs(reader: BlockReader) -> List[VertexIdx]:
    """
    Read and parse vertex indices from a BlockReader.

    Consumes the `vertex_idxs` sub-block and returns a list of VertexIdx objects.

    Args:
        reader (BlockReader): Reader positioned at a vertex indices block.

    Returns:
        List[VertexIdx]: The parsed vertex indices.
    """
    with reader.sub_block(TokenID.vertex_idxs) as vertex_idxs_block:
        vertex_idxs: List[VertexIdx] = []
        count = vertex_idxs_block.read_int()
        
        for _ in range(count // 3):
            reader.report_progress("Reading vertex idxs...")

            vertex1_index = vertex_idxs_block.read_int()
            vertex2_index = vertex_idxs_block.read_int()
            vertex3_index = vertex_idxs_block.read_int()

            vertex_idxs.append(VertexIdx(
                vertex1_index=vertex1_index,
                vertex2_index=vertex2_index,
                vertex3_index=vertex3_index
            ))

        vertex_idxs_block.verify_count(count // 3, len(vertex_idxs))

        return vertex_idxs


def read_normal_idxs(reader: BlockReader) -> List[NormalIdx]:
    """
    Read and parse normal indices from a BlockReader.

    Consumes the `normal_idxs` sub-block and returns a list of NormalIdx objects.

    Args:
        reader (BlockReader): Reader positioned at a normal indices block.

    Returns:
        List[NormalIdx]: The parsed normal indices.
    """
    with reader.sub_block(TokenID.normal_idxs) as normal_idxs_block:
        normal_idxs: List[NormalIdx] = []
        count = normal_idxs_block.read_int()
        
        for _ in range(count):
            reader.report_progress("Reading normal idxs...")

            index = normal_idxs_block.read_int()
            unknown2 = normal_idxs_block.read_int()

            normal_idxs.append(NormalIdx(
                index=index,
                unknown2=unknown2
            ))

        normal_idxs_block.verify_count(count, len(normal_idxs))

        return normal_idxs


def read_flags(reader: BlockReader) -> List[int]:
    """
    Read and parse flag values from a BlockReader.

    Consumes the `flags` sub-block and returns a list of integers.

    Args:
        reader (BlockReader): Reader positioned at a flags block.

    Returns:
        List[int]: The parsed flag values.
    """
    with reader.sub_block(TokenID.flags) as flags_block:
        flags: List[int] = []
        count = flags_block.read_int()
        
        for _ in range(count):
            reader.report_progress("Reading flags...")

            flags.append(flags_block.read_flags())

        flags_block.verify_count(count, len(flags))

        return flags


def read_animations(reader: BlockReader) -> List[Animation]:
    """
    Read and parse animations from a BlockReader.

    Consumes the `animations` sub-block and returns a list of Animation objects.

    Args:
        reader (BlockReader): Reader positioned at an animations block.

    Returns:
        List[Animation]: The parsed animations.
    """
    with reader.sub_block(TokenID.animations) as animations_block:
        animations: List[Animation] = []
        count = animations_block.read_int()
        
        for animation_block in animations_block:
            animation_block.verify_id(TokenID.animation)

            frame_count = animation_block.read_int()
            frame_rate = animation_block.read_int()
            animation_nodes = read_anim_nodes(animation_block)
            
            animation = Animation(
                frame_count=frame_count,
                frame_rate=frame_rate,
                animation_nodes=animation_nodes
            )
            animations.append(animation)

        animations_block.verify_count(count, len(animations))

        return animations


def read_anim_nodes(reader: BlockReader) -> List[AnimationNode]:
    """
    Read and parse animation nodes from a BlockReader.

    Consumes the `anim_nodes` sub-block and returns a list of AnimationNode objects.

    Args:
        reader (BlockReader): Reader positioned at an animation nodes block.

    Returns:
        List[AnimationNode]: The parsed animation nodes.
    """
    with reader.sub_block(TokenID.anim_nodes) as anim_nodes_block:
        anim_nodes: List[AnimationNode] = []
        count = anim_nodes_block.read_int()
        
        for anim_node_block in anim_nodes_block:
            reader.report_progress("Reading animation nodes...")

            anim_node_block.verify_id(TokenID.anim_node)

            name = anim_node_block.label
            controllers = read_controllers(anim_node_block)
            
            anim_node = AnimationNode(
                name=name,
                controllers=controllers
            )
            anim_nodes.append(anim_node)

        anim_nodes_block.verify_count(count, len(anim_nodes))

        return anim_nodes


def read_controllers(reader: BlockReader) -> List[Controller]:
    """
    Read and parse controllers from a BlockReader.

    Consumes the `controllers` sub-block and returns a list of Controller objects.

    Args:
        reader (BlockReader): Reader positioned at a controllers block.

    Returns:
        List[Controller]: The parsed controllers.
    """
    with reader.sub_block(TokenID.controllers) as controllers_block:
        controllers: List[Controller] = []
        count = controllers_block.read_int()
        
        for controller_block in controllers_block:
            keyframes = read_keypositions(controller_block)

            if controller_block.id == TokenID.tcb_rot:
                controllers.append(TCBRot(
                    keyframes=keyframes
                ))
            
            elif controller_block.id == TokenID.linear_pos:
                controllers.append(LinearPos(
                    keyframes=keyframes
                ))
            
            elif controller_block.id == TokenID.tcb_pos:
                controllers.append(TCBPos(
                    keyframes=keyframes
                ))
            
            else:
                logger.warning(f"Unhandled controller: {controller_block.id.name} (id: {controller_block.id})")
                controller_block.skip()

        controllers_block.verify_count(count, len(controllers))

        return controllers


def read_keypositions(reader: BlockReader) -> List[KeyPosition]:
    """
    Read and parse keyframe positions from a BlockReader.

    Consumes keyframe blocks and returns a list of KeyPosition objects.

    Args:
        reader (BlockReader): Reader positioned at keyframe data.

    Returns:
        List[KeyPosition]: The parsed key positions.
    """
    keypositions: List[KeyPosition] = []
    count = reader.read_int()

    for keyposition_block in reader:
        if keyposition_block.id == TokenID.tcb_key:
            frame = keyposition_block.read_int()
            x = keyposition_block.read_float()
            y = keyposition_block.read_float()
            z = keyposition_block.read_float()
            w = keyposition_block.read_float()
            tension = keyposition_block.read_float()
            continuity = keyposition_block.read_float()
            bias = keyposition_block.read_float()
            ease_in = keyposition_block.read_float()
            ease_out = keyposition_block.read_float()

            keypositions.append(TCBKey(
                frame=frame,
                x=x,
                y=y,
                z=z,
                w=w,
                tension=tension,
                continuity=continuity,
                bias=bias,
                ease_in=ease_in,
                ease_out=ease_out
            ))
        
        elif keyposition_block.id == TokenID.linear_key:
            frame = keyposition_block.read_int()
            x = keyposition_block.read_float()
            y = keyposition_block.read_float()
            z = keyposition_block.read_float()

            keypositions.append(LinearKey(
                frame=frame,
                x=x,
                y=y,
                z=z
            ))
        
        elif keyposition_block.id == TokenID.slerp_rot:
            frame = keyposition_block.read_int()
            x = keyposition_block.read_float()
            y = keyposition_block.read_float()
            z = keyposition_block.read_float()
            w = keyposition_block.read_float()

            keypositions.append(SlerpRot(
                frame=frame,
                x=x,
                y=y,
                z=z,
                w=w
            ))
        
        else:
            logger.warning(f"Unhandled keyposition: {keyposition_block.id.name} (id: {keyposition_block.id})")
            keyposition_block.skip()

    reader.verify_count(count, len(keypositions))

    return keypositions