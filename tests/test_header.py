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

import pytest
import simisa


def test_peek_header_uncompressed_shape(global_storage):
    header = simisa.peek_header(global_storage["shapefile_path"])
    assert header.startswith("SIMISA@@")


def test_peek_header_compressed_shape(global_storage):
    header = simisa.peek_header(global_storage["shapefile_compressed_path"])
    assert header.startswith("SIMISA@F")


def test_peek_header_emptyfile(global_storage):
    header = simisa.peek_header(global_storage["emptyfile_path"])
    assert header is None


def test_peek_header_garbagefile(global_storage):
    header = simisa.peek_header(global_storage["garbagefile_path"])
    assert header is None


def test_is_compressed_uncompressed_shape(global_storage):
    is_compressed = simisa.is_compressed(global_storage["shapefile_path"])
    assert not is_compressed


def test_is_compressed_compressed_shape(global_storage):
    is_compressed = simisa.is_compressed(global_storage["shapefile_compressed_path"])
    assert is_compressed


def test_is_compressed_uncompressed_worldfile(global_storage):
    is_compressed = simisa.is_compressed(global_storage["worldfile_path"])
    assert not is_compressed


def test_is_compressed_compressed_worldfile(global_storage):
    is_compressed = simisa.is_compressed(global_storage["worldfile_compressed_path"])
    assert is_compressed


def test_is_compressed_emptyfile(global_storage):
    is_compressed = simisa.is_compressed(global_storage["emptyfile_path"])
    assert is_compressed is None


def test_is_compressed_garbagefile(global_storage):
    is_compressed = simisa.is_compressed(global_storage["garbagefile_path"])
    assert is_compressed is None


def test_is_utf16le_uncompressed_shape(global_storage):
    is_utf16le = simisa.is_utf16le(global_storage["shapefile_path"])
    assert is_utf16le


def test_is_utf16le_compressed_worldfile(global_storage):
    is_utf16le = simisa.is_utf16le(global_storage["worldfile_compressed_path"])
    assert not is_utf16le


def test_is_utf16le_emptyfile(global_storage):
    is_utf16le = simisa.is_utf16le(global_storage["emptyfile_path"])
    assert not is_utf16le


def test_is_utf16le_garbagefile(global_storage):
    is_utf16le = simisa.is_utf16le(global_storage["garbagefile_path"])
    assert not is_utf16le


def test_peek_subheader_uncompressed_shape(global_storage):
    subheader = simisa.peek_subheader(global_storage["shapefile_path"])
    assert subheader == "JINX0s1t"


def test_peek_subheader_compressed_worldfile(global_storage):
    subheader = simisa.peek_subheader(global_storage["worldfile_compressed_path"])
    assert subheader == "JINX0w0b"


def test_peek_subheader_emptyfile(global_storage):
    subheader = simisa.peek_subheader(global_storage["emptyfile_path"])
    assert subheader is None


def test_peek_subheader_garbagefile(global_storage):
    subheader = simisa.peek_subheader(global_storage["garbagefile_path"])
    assert subheader is None


def test_is_binary_uncompressed_shape(global_storage):
    is_binary = simisa.is_binary(global_storage["shapefile_path"])
    assert not is_binary


def test_is_binary_compressed_worldfile(global_storage):
    is_binary = simisa.is_binary(global_storage["worldfile_compressed_path"])
    assert is_binary


def test_is_binary_emptyfile(global_storage):
    is_binary = simisa.is_binary(global_storage["emptyfile_path"])
    assert is_binary is None


def test_is_binary_garbagefile(global_storage):
    is_binary = simisa.is_binary(global_storage["garbagefile_path"])
    assert is_binary is None


def test_is_text_uncompressed_shape(global_storage):
    is_text = simisa.is_text(global_storage["shapefile_path"])
    assert is_text


def test_is_text_compressed_worldfile(global_storage):
    is_text = simisa.is_text(global_storage["worldfile_compressed_path"])
    assert not is_text


def test_is_text_emptyfile(global_storage):
    is_text = simisa.is_text(global_storage["emptyfile_path"])
    assert is_text is None


def test_is_text_garbagefile(global_storage):
    is_text = simisa.is_text(global_storage["garbagefile_path"])
    assert is_text is None


def test_read_filetype_uncompressed_shape(global_storage):
    filetype = simisa.read_filetype(global_storage["shapefile_path"])
    assert filetype == 's'


def test_read_filetype_compressed_worldfile(global_storage):
    filetype = simisa.read_filetype(global_storage["worldfile_compressed_path"])
    assert filetype == 'w'


def test_read_filetype_emptyfile(global_storage):
    filetype = simisa.read_filetype(global_storage["emptyfile_path"])
    assert filetype is None


def test_read_filetype_garbagefile(global_storage):
    filetype = simisa.read_filetype(global_storage["garbagefile_path"])
    assert filetype is None


def test_read_fileversion_uncompressed_shape(global_storage):
    fileversion = simisa.read_fileversion(global_storage["shapefile_path"])
    assert fileversion == 1


def test_read_fileversion_compressed_worldfile(global_storage):
    fileversion = simisa.read_fileversion(global_storage["worldfile_compressed_path"])
    assert fileversion == 0


def test_read_fileversion_emptyfile(global_storage):
    fileversion = simisa.read_fileversion(global_storage["emptyfile_path"])
    assert fileversion is None


def test_read_fileversion_garbagefile(global_storage):
    fileversion = simisa.read_fileversion(global_storage["garbagefile_path"])
    assert fileversion is None
