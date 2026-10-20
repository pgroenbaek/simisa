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
import zlib
import codecs
import struct
import logging
import inspect
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Optional, BinaryIO, TextIO, Callable, Any, Union

from .format import BlockFormat
from .token_id import TokenID
from .verbose import VerbosityLevel, normalize_verbosity, verbose_print

logger = logging.getLogger(__name__)



class BlockWriterError(Exception):
    """Raised when a block writer encounters an error or malformed data."""
    pass


class CompressedStreamWriter(io.RawIOBase):
    """
    File-like wrapper that compresses data on-the-fly using the DEFLATE algorithm via zlib.

    Compatible with Python IO wrappers such as `TextIOWrapper` and `BufferedWriter`.
    """
    def __init__(self, fileobj):
        self.fileobj = fileobj
        self.compressor = zlib.compressobj(level=6, wbits=zlib.MAX_WBITS)
        self._closed = False

    def writable(self):
        return True
    
    @property
    def closed(self):
        return self._closed

    def write(self, data: bytes):
        if self._closed:
            raise ValueError("write to closed file")

        if not data:
            return 0

        compressed = self.compressor.compress(data)

        if compressed:
            self.fileobj.write(compressed)
        
        return len(data)

    def flush(self):
        if self._closed:
            return

        self.fileobj.flush()

    def close(self):
        if not self._closed:
            try:
                tail = self.compressor.flush(zlib.Z_FINISH)

                if tail:
                    self.fileobj.write(tail)
                
                self.fileobj.flush()
            finally:
                self.fileobj.close()
                self.compressor = None
                self._closed = True
        
        super().close()


class BlockWriter(ABC):
    """
    Structured streaming writer for SIMISA block files.

    Provides methods to create and write SIMISA streams with support for:
    - Compressed (zlib DEFLATE) or uncompressed output
    - UTF-16 LE or ASCII encoding
    - Binary or text formatting
    - Structured block and element writing

    Supports writing to both files and in-memory strings. File output is
    configured automatically based on the specified file type, version,
    encoding, and compression settings.

    Use `open()` to create a writer for a file on disk, or `to_string()`
    to generate SIMISA text data in memory without creating a file.
    """

    @staticmethod
    def open(
        filepath: str,
        *,
        filetype: str,
        fileversion: int,
        is_binary: bool = False,
        is_unicode: bool = True,
        is_compressed: bool = False,
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ) -> "BlockWriter":
        """
        Open a file for writing and construct an appropriate BlockWriter.

        This method writes the SIMISA header and subheader, configures the
        output stream according to the specified format, and returns either
        a `BinaryFileWriter` or `TextFileWriter`.

        Args:
            filepath (str): Path to the file to create.
            filetype (str): SIMISA file type identifier.
            fileversion (int): SIMISA file version.
            is_binary (bool, optional): Whether to write binary data. Defaults to False.
            is_unicode (bool, optional): Whether to use UTF-16 LE encoding. Defaults to True.
            is_compressed (bool, optional): Whether to compress the output. Defaults to False.
            verbose: Optional verbosity level.

        Returns:
            BlockWriter: Instance of `BinaryFileWriter` or `TextFileWriter`.

        Raises:
            TypeError: If any parameter has an unexpected type.
            OSError: If the file cannot be opened.
        """
        check_params = (
            ("filepath", filepath, str),
            ("filetype", filetype, str),
            ("fileversion", fileversion, int),
            ("is_binary", is_binary, bool),
            ("is_unicode", is_unicode, bool),
            ("is_compressed", is_compressed, bool),
        )

        for name, value, typ in check_params:
            if isinstance(value, typ):
                continue

            raise TypeError(
                f"Parameter '{name}' must be {typ.__name__}, "
                f"but got {type(value).__name__}"
            )
        
        vlevel = normalize_verbosity(verbose)
        fileformat = 'b' if is_binary else 't'
        subheader = f"JINX0{filetype}{fileversion}{fileformat}______\r\n"
        encoding = "utf-16-le" if is_unicode else "ascii"

        verbose_print(
            "writer",
            f"Opening '{filepath}' for writing (format={'binary' if is_binary else 'text'}, "
            f"unicode={is_unicode}, compressed={is_compressed})",
            VerbosityLevel.NORMAL,
            vlevel
        )

        f = open(filepath, "wb")

        if is_unicode:
            f.write(codecs.BOM_UTF16_LE)
        
        if is_compressed:
            f.write("SIMISA@F".encode(encoding))
            f.write(b"\x00" * 4)
            f.write("@@@@".encode(encoding))
            stream = CompressedStreamWriter(f)
        else:
            f.write("SIMISA@@@@@@@@@@".encode(encoding))
            stream = f

        stream.write(subheader.encode(encoding))
        verbose_print(
            "header",
            f"Wrote header: '{'SIMISA@F' if is_compressed else 'SIMISA@@@@@@@@@@'}', subheader: '{subheader.strip()}'",
            VerbosityLevel.NORMAL,
            vlevel
        )

        if is_binary:
            token_offset = 300 if filetype == "w" else 0
            return BinaryFileWriter(stream, filepath, token_offset, is_unicode, is_compressed, verbose=verbose)

        return TextFileWriter(stream, filepath, encoding, is_compressed, verbose=verbose)
    
    @staticmethod
    def to_string(
        write_fn: Callable[["BlockWriter"], Any],
        *,
        filetype: str,
        fileversion: int,
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ) -> str:
        """
        Generate SIMISA text data in memory using a callback.

        This method creates an uncompressed text stream, writes the SIMISA
        header and subheader, and invokes the callback with a `TextFileWriter`.

        Args:
            write_fn (Callable): Function that receives a BlockWriter and writes
                the desired content.
            filetype (str): SIMISA file type identifier.
            fileversion (int): SIMISA file version.
            verbose: Optional verbosity level.

        Returns:
            str: The generated SIMISA text data.

        Raises:
            TypeError: If a parameter has an unexpected type or `write_fn`
                does not accept a positional first parameter.
        """
        check_params = (
            ("filetype", filetype, str),
            ("fileversion", fileversion, int),
        )

        for name, value, typ in check_params:
            if isinstance(value, typ):
                continue

            raise TypeError(
                f"Parameter '{name}' must be {typ.__name__}, "
                f"but got {type(value).__name__}"
            )
        
        write_fn_params = list(inspect.signature(write_fn).parameters.values())

        positional_params = (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )

        if not write_fn_params or write_fn_params[0].kind not in positional_params:
            raise TypeError("'write_fn' must accept a BlockWriter as its first parameter")

        vlevel = normalize_verbosity(verbose)
        stream = io.StringIO()

        writer = TextFileWriter(stream, filepath="<string>", encoding="utf-8", is_compressed=False, verbose=verbose)

        header = "SIMISA@@@@@@@@@@"
        subheader = f"JINX0{filetype}{fileversion}t______\r\n"

        stream.write(header)
        stream.write(subheader)
        verbose_print(
            "header",
            f"Wrote string header: '{header}', subheader: '{subheader.strip()}'",
            VerbosityLevel.NORMAL,
            vlevel
        )

        write_fn(writer)
        writer.flush()

        text = stream.getvalue()
        writer.close()

        return text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.flush()
        self.close()

    @contextmanager
    def sub_block(self, block_id: TokenID, block_label: Optional[str] = None, block_format: Optional[BlockFormat] = None):
        sub_block = self.begin_sub_block(block_id, block_label, block_format)

        try:
            yield sub_block
        finally:
            sub_block.end_sub_block()

    @abstractmethod
    def begin_sub_block(self, block_id: TokenID, block_label: Optional[str] = None, block_format: Optional[BlockFormat] = None):
        pass

    @abstractmethod
    def end_sub_block(self):
        pass
    
    @abstractmethod
    def write_count(self, value: int):
        pass

    @abstractmethod
    def write_flags(self, value: int):
        pass

    @abstractmethod
    def write_int(self, value: int):
        pass

    @abstractmethod
    def write_uint(self, value: int):
        pass

    @abstractmethod
    def write_float(self, value: float):
        pass

    @abstractmethod
    def write_string(self, value: str):
        pass

    @abstractmethod
    def write_comment(self, text: str):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def flush(self):
        pass


class TextBlockWriter(BlockWriter):

    def __init__(
        self,
        stream: Optional[Union[io.TextIOBase, io.StringIO]] = None,
        parent: Optional['TextBlockWriter'] = None,
        encoding: str = "utf-8",
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ):
        self.stream = stream
        self.parent = parent
        self.encoding = encoding
        self.depth = parent.depth if parent else 0
        self.indent_char = "\t"
        self.block_format: Optional[BlockFormat] = BlockFormat()
        self._buffer: List[str] = []
        self._writing_block = False
        self._items_on_line = 0
        self._items_total = 0
        self._lines_written = 0
        self._written_bytes = 0
        self._closed = False
        self.verbosity: VerbosityLevel = normalize_verbosity(verbose) if verbose is not None else (parent.verbosity if parent else normalize_verbosity(None))

    def _trim_trailing_whitespace(self, trim_chars=None):
        if self.block_format.allow_space_at_line_end:
            if trim_chars is not None:
                trim_chars = trim_chars.replace(" ", "")
            else:
                trim_chars = "\t\r\n\v\f"

        while self._buffer:
            if trim_chars is not None:
                trimmed = self._buffer[-1].rstrip(trim_chars)
            else:
                trimmed = self._buffer[-1].rstrip()

            if trimmed:
                self._buffer[-1] = trimmed
                break

            self._buffer.pop()

    def _write_indent(self):
        if not self.block_format.disable_inner_indent:
            indent = self.indent_char * self.depth

            if indent:
                self._buffer.append(indent)

    def _write_newline(self):
        if self.parent is not None:
            self.parent._trim_trailing_whitespace(trim_chars=" ")

        if self.block_format.allow_space_at_line_end:
            if self._buffer and self._buffer[-1] and not self._buffer[-1].endswith(" "):
                self._buffer.append(" ")
            
            self._trim_trailing_whitespace(trim_chars="\t\r\n\v\f")
        else:
            self._trim_trailing_whitespace()

        self._buffer.append("\r\n")
        self._write_indent()
        self._items_on_line = 0


    def _write_value(self, text: str):
        if not isinstance(text, str):
            raise TypeError(f"Parameter 'text' must be str, but got {type(value).__name__}")
        
        if self._lines_written == 0 and self.block_format.max_items_first_line is not None:
            if self._items_on_line >= self.block_format.max_items_first_line:
                self._write_newline()
                self._lines_written += 1

        elif self.block_format.max_items_per_line is not None:
            if self._items_on_line >= self.block_format.max_items_per_line:
                self._write_newline()
                self._lines_written += 1

        self._write_token(text)
        self._items_on_line += 1
        self._items_total += 1

    def _write_token(self, text: str):
        if not isinstance(text, str):
            raise TypeError(f"Parameter 'text' must be str, but got {type(text).__name__}")

        if not self.block_format.allow_space_at_line_end:
            self._trim_trailing_whitespace(trim_chars=" ")

        if self._buffer:
            last = self._buffer[-1]
            if last and not last[-1].isspace():
                self._buffer.append(" ")

        self._buffer.append(text)
        
    def begin_sub_block(
        self,
        block_id: TokenID,
        block_label: Optional[str] = None,
        block_format: Optional[BlockFormat] = None
    ):
        if self._closed:
            raise ValueError("Cannot begin sub-block on a closed writer")

        if block_format is None:
            block_format = BlockFormat()

        if block_format.newline_before_block:
            self._write_newline()
        
        if self._lines_written == 0 and self.block_format.max_items_first_line is not None:
            if self._items_on_line >= self.block_format.max_items_first_line:
                self._write_newline()
                self._lines_written += 1

        elif self.block_format.max_items_per_line is not None:
            if self._items_on_line >= self.block_format.max_items_per_line:
                self._write_newline()
                self._lines_written += 1

        self._items_on_line += 1
        self._items_total += 1

        sub_block = TextBlockWriter(
            stream=self.stream,
            parent=self,
            encoding=self.encoding,
            verbose=self.verbosity
        )

        sub_block.block_format = block_format
        sub_block._writing_block = True
        sub_block.block_id = block_id
        
        verbose_print(
            "block",
            f"Writing block: '{block_id.name}'" + (f" (label: {block_label})" if block_label else ""),
            VerbosityLevel.NORMAL if self.depth == 0 else VerbosityLevel.DETAILED,
            self.verbosity
        )

        sub_block._write_token(f"{block_id.name}")

        if block_label is not None:
            sub_block._write_token(f"{block_label}")

        if sub_block.block_format.newline_before_start:
            sub_block._write_newline()

        sub_block._write_token("(")

        if not self.block_format.disable_inner_depth_increment:
            sub_block.depth = self.depth + 1
        
        if sub_block.block_format.newline_after_start:
            sub_block._write_newline()

        return sub_block
        
    def end_sub_block(self):
        if not self._writing_block or self._closed:
            return
        
        verbose_print(
            "block",
            f"End of block: '{getattr(self, 'block_id', None).name if getattr(self, 'block_id', None) else '<unknown>'}'",
            VerbosityLevel.DETAILED,
            self.verbosity
        )

        self.depth -= 1

        if self.block_format.newline_before_closing:
            if self._items_total != 0 and not self.block_format.enable_zero_count_newline:
                self._write_newline()

        self._write_token(")")

        if self.block_format.newline_after_closing:
            self._write_newline()

        self._writing_block = False
        self._closed = True

        block_text = "".join(self._buffer).rstrip(" ")

        if self.parent is not None:
            self.parent._trim_trailing_whitespace(trim_chars=" ")

            if self.parent._buffer and block_text:
                last = self.parent._buffer[-1]

                if last and not last[-1].isspace() and not block_text[0].isspace():
                    self.parent._buffer.append(" ")

            self.parent._buffer.append(block_text)

        elif self.stream is not None:
            encoded_text = block_text.encode(self.encoding)

            if isinstance(self.stream, io.TextIOBase):
                self.stream.write(block_text)
            else:
                self.stream.write(encoded_text)
            
            self._written_bytes += len(encoded_text)
        
        else:
            raise BlockWriterError("No output stream set for root writer, and no parent-writer.")

        self._buffer = []

    def write_count(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write count: {value}", VerbosityLevel.DEBUG, self.verbosity)

        if value == 0 and not self.block_format.enable_zero_count_newline:
            self._write_token(str(value))

        else:
            if self.block_format.newline_before_count:
                self._write_newline()

            self._write_token(str(value))

            if self.block_format.newline_after_count:
                self._write_newline()

    def write_flags(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write flags: 0x{value:08x}", VerbosityLevel.DEBUG, self.verbosity)
        self._write_value(f"{value:08x}")

    def write_int(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write int: {value}", VerbosityLevel.DEBUG, self.verbosity)
        self._write_value(str(value))

    def write_uint(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write uint: {value}", VerbosityLevel.DEBUG, self.verbosity)
        self._write_value(str(value))

    def write_float(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"Parameter 'value' must be float or int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write float: {value}", VerbosityLevel.DEBUG, self.verbosity)
        if float(value).is_integer(): # Allow .0 fractions to be omitted
            text = str(int(value))
        else:
            text = str(value)

            if "e" in text.lower(): # Convert scientific notation exponent to three decimal places
                mantissa, exponent = text.lower().split("e")
                text = f"{mantissa}e{int(exponent):+04d}".replace("e+", "e")

        self._write_value(text)

    def write_string(self, value: str):
        if not isinstance(value, str):
            raise TypeError(f"Parameter 'value' must be str, but got {type(value).__name__}")
        
        verbose_print("write", f"Write string: '{value}'", VerbosityLevel.DEBUG, self.verbosity)
        self._write_value(value)

    def write_comment(self, text: str):
        if not isinstance(text, str):
            raise TypeError(f"Parameter 'text' must be str, but got {type(text).__name__}")
        
        verbose_print("write", f"Write comment: '{text}'", VerbosityLevel.DEBUG, self.verbosity)
        self._write_token("_SKIP")

        if self.block_format.newline_before_start:
            self._write_newline()

        self._write_token("(")
        
        if self.block_format.newline_after_start:
            self._write_newline()
        
        self._write_token(f"{text}")

        if self.block_format.newline_before_closing:
            self._write_newline()

        self._write_token(")")

        if self.block_format.newline_after_closing:
            self._write_newline()

    def flush(self):
        if self._closed:
            return

        if self.stream is not None and self._buffer:
            self._trim_trailing_whitespace()

            content = "".join(self._buffer)
            self._buffer = []

            encoded_text = content.encode(self.encoding)

            if isinstance(self.stream, io.TextIOBase):
                self.stream.write(content)
            else:
                self.stream.write(encoded_text)
            
            self._written_bytes += len(encoded_text)

            self.stream.flush()

    def close(self):
        if self._closed:
            return

        self.flush()
        self._closed = True


class TextFileWriter(TextBlockWriter):

    def __init__(
        self,
        stream: Union[io.TextIOBase, io.StringIO],
        filepath: str,
        encoding="utf-8",
        is_compressed: bool = False,
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ):
        super().__init__(
            stream=stream,
            parent=None,
            encoding=encoding,
            verbose=verbose
        )
        self.filepath = filepath
        self.is_compressed = is_compressed
        self.is_closed = False

    def flush(self):
        super().flush()
        self.is_closed = self._closed

    def close(self):
        if self.is_closed:
            return

        super().close()

        self.stream.flush()
        self.stream.close()

        self.is_closed = True

        if self.is_compressed: # Patch uncompressed size into header if compressed.
            is_unicode = self.encoding in ("utf-16-le", "UTF-16-LE")
            if is_unicode:
                header_size = 64 + 2
            else:
                header_size = 32
            
            uncompressed_size = header_size + self._written_bytes

            with open(self.filepath, "r+b") as f:
                size_position = 18 if is_unicode else 8
                f.seek(size_position) # After SIMISA@F
                f.write(uncompressed_size.to_bytes(4, "little"))

            verbose_print(
                "writer",
                f"Patched uncompressed size ({uncompressed_size} bytes) in '{self.filepath}'",
                VerbosityLevel.DETAILED,
                self.verbosity
            )

        verbose_print("writer", f"Closed writer for '{self.filepath}'", VerbosityLevel.NORMAL, self.verbosity)


class BinaryBlockWriter(BlockWriter):
    _UINT32 = struct.Struct("<I")
    _INT32 = struct.Struct("<i")
    _UINT16 = struct.Struct("<H")
    _FLOAT32 = struct.Struct("<f")
    _BLOCK_HEADER = struct.Struct("<HHI")

    def __init__(
        self,
        stream: Optional[BinaryIO],
        parent: Optional["BinaryBlockWriter"] = None,
        token_offset: int = 0,
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ):
        self.stream = stream
        self.parent = parent
        self.token_offset = token_offset
        self.id: Optional[TokenID] = None
        self.flags: int = 0
        self.label: Optional[str] = None
        self._buffer = io.BytesIO()
        self._writing_block: bool = False
        self._written_bytes: int = 0
        self.verbosity: VerbosityLevel = normalize_verbosity(verbose) if verbose is not None else (parent.verbosity if parent else normalize_verbosity(None))

    def _write_bytes(self, data: bytes) -> None:
        self._buffer.write(data)

    def begin_sub_block(
        self,
        block_id: TokenID,
        block_label: Optional[str] = None,
        block_format: Optional[BlockFormat] = None
    ):
        sub_block = BinaryBlockWriter(
            stream=self.stream,
            parent=self,
            token_offset=self.token_offset,
            verbose=self.verbosity
        )

        sub_block.label = block_label
        sub_block.id = block_id
        sub_block._writing_block = True

        verbose_print(
            "block",
            f"Writing binary block: '{block_id.name}'" + (f" (label: {block_label})" if block_label else ""),
            VerbosityLevel.NORMAL if self.parent is None else VerbosityLevel.DETAILED,
            self.verbosity
        )

        return sub_block

    def end_sub_block(self):
        if not self._writing_block:
            return

        self._writing_block = False

        payload = self._buffer.getvalue()

        if self.label:
            encoded_label = self.label.encode("utf-16-le")
            label_bytes = bytes([len(self.label)]) + encoded_label
        else:
            label_bytes = b"\x00"

        size = len(label_bytes) + len(payload)
        raw_id = self.id.value - self.token_offset

        header_bytes = self._BLOCK_HEADER.pack(raw_id, self.flags, size)
        block_bytes = header_bytes + label_bytes + payload

        verbose_print(
            "block",
            f"End of binary block: '{self.id.name if self.id else '<unknown>'}' (size={size})",
            VerbosityLevel.DETAILED,
            self.verbosity
        )

        if self.parent is not None:
            self.parent._buffer.write(block_bytes)

        elif self.stream is not None:
            self.stream.write(block_bytes)
        
        else:
            raise BlockWriterError("No output stream set for root writer, and no parent-writer.")

    def write_count(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write count: {value}", VerbosityLevel.DEBUG, self.verbosity)
        self.write_int(value)

    def write_flags(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write flags: 0x{value:08x}", VerbosityLevel.DEBUG, self.verbosity)
        self._write_bytes(self._UINT32.pack(value))

    def write_int(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write int: {value}", VerbosityLevel.DEBUG, self.verbosity)
        self._write_bytes(self._INT32.pack(value))

    def write_uint(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError(f"Parameter 'value' must be int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write uint: {value}", VerbosityLevel.DEBUG, self.verbosity)
        self._write_bytes(self._UINT32.pack(value))

    def write_float(self, value: float) -> None:
        if not isinstance(value, (int, float)):
            raise TypeError(f"Parameter 'value' must be float or int, but got {type(value).__name__}")
        
        verbose_print("write", f"Write float: {value}", VerbosityLevel.DEBUG, self.verbosity)
        self._write_bytes(self._FLOAT32.pack(value))

    def write_string(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Parameter 'value' must be str, but got {type(value).__name__}")
        
        verbose_print("write", f"Write string: '{value}'", VerbosityLevel.DEBUG, self.verbosity)
        if not value:
            self._write_bytes(self._UINT16.pack(0))
            return
        
        encoded = value.encode("utf-16-le")

        self._write_bytes(self._UINT16.pack(len(value)))
        self._write_bytes(encoded)

    def write_comment(self, text: str):
        if not isinstance(text, str):
            raise TypeError(f"Parameter 'text' must be str, but got {type(text).__name__}")
        verbose_print("write", f"Write comment: '{text}'", VerbosityLevel.DEBUG, self.verbosity)

    def flush(self):
        if self.stream:
            self.stream.flush()

    def close(self):
        if self.stream and not self.stream.closed:
            self.stream.close()


class BinaryFileWriter(BinaryBlockWriter):

    def __init__(
        self,
        stream: BinaryIO,
        filepath: str,
        token_offset: int = 0,
        is_unicode: bool = False,
        is_compressed: bool = False,
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ):
        super().__init__(
            stream=stream,
            parent=None,
            token_offset=token_offset,
            verbose=verbose
        )
        self.filepath = filepath
        self.is_unicode = is_unicode
        self.is_compressed = is_compressed
        self.is_closed = False

    def _write(self, data: bytes) -> None:
        if self.stream is None:
            raise BlockWriterError("No output stream set")
        
        self.stream.write(data)

    def flush(self):
        if not self.is_closed and self.stream:
            self.stream.flush()

    def close(self):
        if self.is_closed or self.stream is None:
            return

        buffered_data = self._buffer.getvalue()

        if buffered_data:
            self.stream.write(buffered_data)

        if not self.stream.closed:
            self.stream.flush()
            self.stream.close()

        self.is_closed = True

        if self.is_compressed: # Patch uncompressed size into header if compressed.
            if self.is_unicode:
                header_size = 64 + 2
            else:
                header_size = 32
            
            uncompressed_size = header_size + self._written_bytes

            with open(self.filepath, "r+b") as f:
                size_position = 18 if self.is_unicode else 8
                f.seek(size_position) # After SIMISA@F
                f.write(uncompressed_size.to_bytes(4, "little"))

            verbose_print(
                "writer",
                f"Patched uncompressed size ({uncompressed_size} bytes) in '{self.filepath}'",
                VerbosityLevel.DETAILED,
                self.verbosity
            )

        verbose_print("writer", f"Closed writer for '{self.filepath}'", VerbosityLevel.NORMAL, self.verbosity)