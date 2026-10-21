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

# TODO Does the unicode/ascii split work?
# TODO Does the text/binary split work?
# TODO Does the text/binary split work?
# TODO error handling in open/to_string
# TODO Does writing values of different types work for text/binary?
# TODO error handling in writing different values
# TODO Does the uncompressed size patching work for text/binary?

import codecs
import inspect
import struct
import zlib
import pytest

from simisa import TokenID
from simisa.writer import (
    BlockWriter,
    BinaryFileWriter,
    TextFileWriter,
)


def open_writer(
    tmp_path,
    *,
    is_binary=False,
    is_utf16le=True,
    is_compressed=False,
    filetype="s",
    fileversion=1,
):
    path = tmp_path / "sample.s"

    writer = BlockWriter.open(
        str(path),
        filetype=filetype,
        fileversion=fileversion,
        is_binary=is_binary,
        is_utf16le=is_utf16le,
        is_compressed=is_compressed,
    )

    return path, writer


def write_blocks(writer):
    with writer.sub_block(TokenID.normals) as normals_block:
        normals_block.write_count(3)

        normals = [
            Vector(0.1, 0.1, 1.1),
            Vector(0.1, 1.1, 0.1),
            Vector(1.1, 0.1, 0.1)
        ]

        for vector in normals:
            with normals_block.sub_block(TokenID.vector) as vector_block:
                vector_block.write_float(vector.x)
                vector_block.write_float(vector.y)
                vector_block.write_float(vector.z)


def write_values(writer):
    writer.write_count(5)
    writer.write_flags(3)
    writer.write_int(-123)
    writer.write_uint(123)
    writer.write_float(1.25)
    writer.write_string("hello")
    writer.write_comment("test comment")


def close_writer(writer):
    writer.flush()
    writer.close()


def find_zlib_stream(data):
    """
    Find a zlib stream embedded after the SIMISA header.

    The header is format-dependent, so scan for a valid zlib
    stream rather than assuming a fixed compressed-data offset.
    """
    for offset in range(len(data)):
        try:
            decompressor = zlib.decompressobj()
            output = decompressor.decompress(data[offset:])
            if decompressor.eof:
                return offset, output
        except zlib.error:
            continue

    pytest.fail("No valid zlib stream found in compressed output")



@pytest.mark.parametrize(
    ("is_binary", "expected_class"),
    [
        (False, TextFileWriter),
        (True, BinaryFileWriter),
    ],
)
def test_open_selects_writer_by_format(tmp_path, is_binary, expected_class):
    path, writer = open_writer(tmp_path, is_binary=is_binary)

    try:
        assert isinstance(writer, expected_class)
    finally:
        writer.close()


@pytest.mark.parametrize("is_utf16le", [True, False])
def test_open_writes_header_in_selected_encoding(tmp_path, is_utf16le):
    path, writer = open_writer(tmp_path, is_utf16le=is_utf16le)
    writer.close()

    data = path.read_bytes()

    if is_utf16le:
        assert data.startswith(codecs.BOM_UTF16_LE)
        assert "SIMISA@@@@@@@@@@".encode("utf-16-le") in data
    else:
        assert data.startswith(b"SIMISA@@@@@@@@@@")


@pytest.mark.parametrize(
    ("is_binary", "is_utf16le", "expected_class"),
    [
        (False, False, TextFileWriter),
        (False, True, TextFileWriter),
        (True, False, BinaryFileWriter),
        (True, True, BinaryFileWriter),
    ],
)
def test_encoding_and_format_options_are_independent(tmp_path, is_binary, is_utf16le, expected_class):
    _, writer = open_writer(
        tmp_path,
        is_binary=is_binary,
        is_utf16le=is_utf16le,
    )

    try:
        assert isinstance(writer, expected_class)
    finally:
        writer.close()


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("filepath", None),
        ("filepath", 123),
        ("filepath", b"sample.s"),
        ("filetype", None),
        ("filetype", 123),
        ("fileversion", None),
        ("fileversion", "1"),
        ("is_binary", 1),
        ("is_utf16le", "true"),
        ("is_compressed", 0),
    ],
)
def test_open_rejects_invalid_parameter_types(tmp_path, parameter, value):
    kwargs = {
        "filepath": str(tmp_path / "sample.s"),
        "filetype": "s",
        "fileversion": 1,
        "is_binary": False,
        "is_utf16le": True,
        "is_compressed": False,
    }
    kwargs[parameter] = value

    with pytest.raises(TypeError):
        BlockWriter.open(**kwargs)


def test_open_directorypath_propagates_os_error(tmp_path):
    with pytest.raises(OSError):
        BlockWriter.open(
            str(tmp_path), # using a directory path here = OSError
            filetype="s",
            fileversion=1,
        )


@pytest.mark.parametrize(
    ("filetype", "fileversion"),
    [
        (None, 1),
        (123, 1),
        ("s", None),
        ("s", "1"),
    ],
)
def test_to_string_rejects_invalid_parameter_types(filetype, fileversion):
    with pytest.raises(TypeError):
        BlockWriter.to_string(
            lambda writer: None,
            filetype=filetype,
            fileversion=fileversion,
        )


@pytest.mark.parametrize(
    "callback",
    [
        None,
        123,
        lambda: None,
        lambda *, writer: None,
    ],
)
def test_to_string_rejects_invalid_callback(callback):
    with pytest.raises(TypeError):
        BlockWriter.to_string(
            callback,
            filetype="s",
            fileversion=1,
        )


def test_to_string_writes_header_and_subheader():
    result = BlockWriter.to_string(
        lambda writer: None,
        filetype="s",
        fileversion=1,
    )

    assert result.startswith("SIMISA@@@@@@@@@@")
    assert "JINX0s1t______\r\n" in result


def test_to_string_passes_writer_to_callback():
    received = []

    def callback(writer):
        received.append(writer)

    BlockWriter.to_string(
        callback,
        filetype="s",
        fileversion=1,
    )

    assert len(received) == 1
    assert isinstance(received[0], TextFileWriter)


def test_to_string_propagates_callback_exception():
    def callback(writer):
        raise RuntimeError("write failed")

    with pytest.raises(RuntimeError, match="write failed"):
        BlockWriter.to_string(
            callback,
            filetype="s",
            fileversion=1,
        )


@pytest.mark.parametrize(
    ("is_binary", "is_utf16le"),
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
def test_write_supported_values(tmp_path, is_binary, is_utf16le):
    path, writer = open_writer(
        tmp_path,
        is_binary=is_binary,
        is_utf16le=is_utf16le,
    )

    try:
        write_values(writer)
        writer.flush()
    finally:
        writer.close()

    assert path.exists()
    assert path.stat().st_size > 0


def test_to_string_writes_supported_text_values():
    result = BlockWriter.to_string(
        write_values,
        filetype="s",
        fileversion=1,
    )

    assert len(result) > len("SIMISA@@@@@@@@@@")
    assert "JINX0s1t______" in result


@pytest.mark.parametrize(
    ("method_name", "invalid_value"),
    [
        ("write_count", "not an integer"),
        ("write_flags", "not an integer"),
        ("write_int", "not an integer"),
        ("write_uint", "not an integer"),
        ("write_float", "not a float"),
        ("write_string", 123),
        ("write_comment", 123),
    ],
)
@pytest.mark.parametrize("is_binary", [False, True])
def test_write_rejects_invalid_value_types(tmp_path, method_name, invalid_value, is_binary):
    _, writer = open_writer(
        tmp_path,
        is_binary=is_binary,
    )

    try:
        with pytest.raises((TypeError, ValueError, struct.error)):
            getattr(writer, method_name)(invalid_value)
    finally:
        writer.close()


@pytest.mark.parametrize(
    ("method_name", "invalid_value"),
    [
        ("write_int", 1 << 100),
        ("write_uint", -1),
        ("write_uint", 1 << 100),
    ],
)
def test_write_rejects_out_of_range_integers(tmp_path, method_name, invalid_value):
    _, writer = open_writer(
        tmp_path,
        is_binary=True,
    )

    try:
        with pytest.raises((ValueError, OverflowError, struct.error)):
            getattr(writer, method_name)(invalid_value)
    finally:
        writer.close()


@pytest.mark.parametrize(
    ("is_binary", "is_utf16le"),
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
def test_compressed_output_is_created(tmp_path, is_binary, is_utf16le):
    path, writer = open_writer(
        tmp_path,
        is_binary=is_binary,
        is_utf16le=is_utf16le,
        is_compressed=True,
    )

    try:
        write_values(writer)
    finally:
        writer.close()

    data = path.read_bytes()

    assert data
    assert (
        data.startswith(b"SIMISA@F") or
        data.startswith(codecs.BOM_UTF16_LE + "SIMISA@F".encode("utf-16-le"))
    )


def test_uncompressed_output_does_not_use_compressed_header(tmp_path):
    path, writer = open_writer(
        tmp_path,
        is_utf16le=False,
        is_compressed=False,
    )
    writer.write_string("payload")
    writer.close()

    data = path.read_bytes()

    assert data
    assert data.startswith(b"SIMISA@@")


@pytest.mark.parametrize("is_binary", [False, True])
@pytest.mark.parametrize("is_utf16le", [False, True])
def test_compressed_stream_contains_written_data(tmp_path, is_binary, is_utf16le):
    path, writer = open_writer(
        tmp_path,
        is_binary=is_binary,
        is_utf16le=is_utf16le,
        is_compressed=True,
    )

    try:
        writer.write_string("size-patching-test")
    finally:
        writer.close()

    data = path.read_bytes()
    _, decompressed = find_zlib_stream(data)

    assert decompressed


# TODO
# @pytest.mark.parametrize("is_binary", [False, True])
# def test_compressed_header_size_matches_uncompressed_data(tmp_path, is_binary):
#     path, writer = open_writer(
#         tmp_path,
#         is_binary=is_binary,
#         is_compressed=True,
#         is_utf16le=False,
#     )

#     try:
#         writer.write_string("known-payload-for-size-check")
#     finally:
#         writer.close()

#     data = path.read_bytes()
#     _, decompressed = find_zlib_stream(data)

#     # compressed files use a four-byte size field after
#     # SIMISA@F in the header. Verify the stored size
#     # against the actual decompressed stream length.
#     declared_size = struct.unpack("<I", data[8:12])[0]
#     header_size = 32

#     assert declared_size == len(decompressed) + header_size