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

import io
import pytest

from simisa import (
    VerbosityLevel,
    normalize_verbosity,
    get_global_verbosity,
    set_global_verbosity,
    set_verbose_output,
    verbose_print,
    BlockReader,
    BlockWriter,
    TokenID,
    peek_header,
    is_compressed,
    peek_first_include,
    resolve_includes,
)


def test_verbosity_level_values():
    assert VerbosityLevel.SILENT == 0
    assert VerbosityLevel.NORMAL == 1
    assert VerbosityLevel.DETAILED == 2
    assert VerbosityLevel.DEBUG == 3


def test_normalize_verbosity():
    assert normalize_verbosity(None) == VerbosityLevel.SILENT
    assert normalize_verbosity(False) == VerbosityLevel.SILENT
    assert normalize_verbosity(True) == VerbosityLevel.NORMAL
    assert normalize_verbosity(0) == VerbosityLevel.SILENT
    assert normalize_verbosity(1) == VerbosityLevel.NORMAL
    assert normalize_verbosity(2) == VerbosityLevel.DETAILED
    assert normalize_verbosity(3) == VerbosityLevel.DEBUG
    assert normalize_verbosity(4) == VerbosityLevel.DEBUG
    assert normalize_verbosity("silent") == VerbosityLevel.SILENT
    assert normalize_verbosity("normal") == VerbosityLevel.NORMAL
    assert normalize_verbosity("detailed") == VerbosityLevel.DETAILED
    assert normalize_verbosity("debug") == VerbosityLevel.DEBUG
    assert normalize_verbosity(VerbosityLevel.DETAILED) == VerbosityLevel.DETAILED

    with pytest.raises(ValueError):
        normalize_verbosity("invalid_level")


def test_global_verbosity():
    original = get_global_verbosity()
    try:
        set_global_verbosity(VerbosityLevel.DETAILED)
        assert get_global_verbosity() == VerbosityLevel.DETAILED
        assert normalize_verbosity(None) == VerbosityLevel.DETAILED

        set_global_verbosity(False)
        assert get_global_verbosity() == VerbosityLevel.SILENT
    finally:
        set_global_verbosity(original)


def test_verbose_print_custom_output():
    buf = io.StringIO()
    set_verbose_output(buf)
    try:
        verbose_print("test", "silent message", VerbosityLevel.NORMAL, VerbosityLevel.SILENT)
        assert buf.getvalue() == ""

        verbose_print("test", "normal message", VerbosityLevel.NORMAL, VerbosityLevel.NORMAL)
        assert "[simisa:test] normal message\n" in buf.getvalue()

        buf.seek(0)
        buf.truncate(0)
        verbose_print("reader", "debug info", VerbosityLevel.DEBUG, VerbosityLevel.NORMAL)
        assert buf.getvalue() == ""

        verbose_print("reader", "debug info", VerbosityLevel.DEBUG, VerbosityLevel.DEBUG)
        assert "[simisa:reader] debug info\n" in buf.getvalue()
    finally:
        set_verbose_output(None)


def test_reader_from_string_silent_by_default(capsys):
    data = "SIMISA@@@@@@@@@@JINX0s1t______\r\nshape ( comment ( ) )"
    reader = BlockReader.from_string(data)
    with reader.sub_block(TokenID.shape) as sub:
        with sub.sub_block(TokenID.comment):
            pass
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_reader_from_string_verbose(capsys):
    data = "SIMISA@@@@@@@@@@JINX0s1t______\r\nshape ( 10 20 )"
    reader = BlockReader.from_string(data, verbose=VerbosityLevel.DEBUG)
    with reader.sub_block(TokenID.shape) as sub:
        val1 = sub.read_int()
        val2 = sub.read_int()
        assert val1 == 10
        assert val2 == 20
    captured = capsys.readouterr()
    assert "[simisa:reader]" in captured.out
    assert "[simisa:block]" in captured.out
    assert "[simisa:read]" in captured.out
    assert "Read int: 10" in captured.out
    assert "Read int: 20" in captured.out


def test_writer_to_string_verbose(capsys):
    def write_body(writer: BlockWriter):
        with writer.sub_block(TokenID.shape) as shape:
            shape.write_int(42)
            shape.write_string("hello")

    out = BlockWriter.to_string(write_body, filetype="s", fileversion=1, verbose=VerbosityLevel.DEBUG)
    assert "hello" in out
    captured = capsys.readouterr()
    assert "[simisa:header]" in captured.out
    assert "[simisa:block]" in captured.out
    assert "[simisa:write]" in captured.out
    assert "Write int: 42" in captured.out
    assert "Write string: 'hello'" in captured.out


def test_file_read_write_verbose(tmp_path, capsys):
    filepath = str(tmp_path / "test.s")

    writer = BlockWriter.open(filepath, filetype="s", fileversion=1, is_binary=False, is_unicode=False, verbose=VerbosityLevel.NORMAL)
    with writer.sub_block(TokenID.shape) as shape:
        shape.write_int(100)
    writer.close()

    captured = capsys.readouterr()
    assert "[simisa:writer]" in captured.out
    assert "[simisa:header]" in captured.out
    assert "[simisa:block]" in captured.out

    reader = BlockReader.open(filepath, verbose=VerbosityLevel.NORMAL)
    with reader.sub_block(TokenID.shape) as shape:
        assert shape.read_int() == 100
    reader.close()

    captured = capsys.readouterr()
    assert "[simisa:reader]" in captured.out
    assert "[simisa:header]" in captured.out


def test_binary_file_read_write_verbose(tmp_path, capsys):
    filepath = str(tmp_path / "test.b")

    writer = BlockWriter.open(filepath, filetype="s", fileversion=1, is_binary=True, is_unicode=False, verbose=VerbosityLevel.DEBUG)
    with writer.sub_block(TokenID.shape, block_label="test_label") as shape:
        shape.write_int(999)
        shape.write_string("world")
    writer.close()

    captured = capsys.readouterr()
    assert "[simisa:writer]" in captured.out
    assert "[simisa:block]" in captured.out
    assert "[simisa:write]" in captured.out

    reader = BlockReader.open(filepath, verbose=VerbosityLevel.DEBUG)
    with reader.sub_block(TokenID.shape) as shape:
        assert shape.label == "test_label"
        assert shape.read_int() == 999
        assert shape.read_string() == "world"
        shape.verify_end_of_block()
    reader.close()

    captured = capsys.readouterr()
    assert "[simisa:reader]" in captured.out
    assert "[simisa:block]" in captured.out
    assert "[simisa:read]" in captured.out


def test_header_and_include_verbose(tmp_path, capsys):
    inc_file = tmp_path / "inc.dat"
    inc_file.write_text("SIMISA@@@@@@@@@@JINX0s1t______\r\n")

    main_file = tmp_path / "main.dat"
    main_file.write_text(f'include ( "{inc_file.name}" )\r\n')

    peek_header(str(inc_file), verbose=VerbosityLevel.NORMAL)
    is_compressed(str(inc_file), verbose=VerbosityLevel.NORMAL)
    peek_first_include(str(main_file))
    resolve_includes(f'include ( "{inc_file.name}" )', str(main_file), verbose=VerbosityLevel.NORMAL)

    captured = capsys.readouterr()
    assert "[simisa:header]" in captured.out
    assert "[simisa:include]" in captured.out
