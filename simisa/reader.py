"""
This file is part of Simisa.

This code is loosely based on `SBR.cs` from the `Orts.Parsers.Msts`
namespace within the Open Rails codebase.

Copyright (C) 2013, 2014, 2015 by the Open Rails project
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
import struct
import codecs
import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Optional, Iterator, BinaryIO, TextIO, Dict, Union

from .header import is_compressed
from .header import SimisaHeaderError, SimisaSubheaderError
from .include import has_includes, peek_first_include
from .include import resolve_includes, UnresolvableIncludeError
from .token_id import TokenID
from .stf import StfReader
from .verbose import VerbosityLevel, normalize_verbosity, verbose_print

logger = logging.getLogger(__name__)



class BlockReaderError(Exception):
    """Raised when a block reader encounters an error or malformed data."""
    pass


class CompressedStreamReader(io.RawIOBase):
    """
    File-like wrapper that decompresses data on-the-fly using the DEFLATE algorithm via zlib.

    Compatible with Python IO wrappers such as `TextIOWrapper` and `BufferedReader`.
    """
    CHUNK_SIZE = 8192

    def __init__(self, fileobj):
        self.fileobj = fileobj
        self.decompressor = zlib.decompressobj(wbits=zlib.MAX_WBITS)
        self._buffer = bytearray()
        self._buffer_position = 0
        self._eof = False

    def readable(self):
        return True
    
    @property
    def closed(self):
        return self.fileobj is None

    def read(self, size=-1):
        if size == 0:
            return b""

        if self._eof and not self._buffer:
            return b""

        if size is None or size < 0:
            return self._read_all()

        return self._read_exact(size)

    def _read_all(self):
        chunks = []

        if self._buffer:
            chunks.append(bytes(self._buffer))
            self._buffer.clear()

        while not self._eof:
            raw = self.fileobj.read(self.CHUNK_SIZE)

            if not raw:
                chunks.append(self.decompressor.flush())
                self._eof = True
                break

            chunks.append(self.decompressor.decompress(raw))

        return b"".join(chunks)

    def _read_exact(self, size):
        out = bytearray()

        if self._buffer:
            available = len(self._buffer) - self._buffer_position
            take = min(size, available)

            out += self._buffer[self._buffer_position:self._buffer_position + take]
            self._buffer_position += take
            size -= take

            if self._buffer_position == len(self._buffer):
                self._buffer.clear()
                self._buffer_position = 0

        while size > 0 and not self._eof:
            raw = self.fileobj.read(self.CHUNK_SIZE)

            if not raw:
                tail = self.decompressor.flush()
                self._buffer.extend(tail)
                self._eof = True
                break

            data = self.decompressor.decompress(raw)

            if not data:
                continue

            if len(data) <= size:
                out += data
                size -= len(data)
            else:
                out += data[:size]
                self._buffer.extend(data[size:])
                size = 0

        return bytes(out)

    def readinto(self, buffer: bytearray) -> int:
        if buffer is None:
            raise TypeError("Parameter 'buffer' must be a writable buffer")

        requested_size = len(buffer)
        data = self.read(requested_size)

        bytes_read = len(data)
        buffer[:bytes_read] = data

        return bytes_read

    def close(self):
        if self.fileobj is not None:
            try:
                self.fileobj.close()
            finally:
                self.fileobj = None
                self.decompressor = None
                self._buffer.clear()
                self._eof = True

        super().close()


class BlockReader(ABC):
    """
    Structured streaming reader for SIMISA block files.

    Provides validated access to a SIMISA stream with support for:
    - Iteration over nested blocks
    - Context-managed sub-block access
    - Validation of block IDs and element counts

    To preserve stream integrity, all data within a block must be either
    read or skipped using `skip()`. Every block must also be explicitly
    closed with `verify_end_of_block()`.

    Calls to `verify_end_of_block()` are performed automatically when using
    the `sub_block()` context manager or any iterator exposed by the reader.

    Supports input streams that are:
    - Compressed (zlib DEFLATE) or uncompressed
    - UTF-16 LE or ASCII encoded
    - Binary or text formatted
    """

    @staticmethod
    def open(filepath: str, verbose: Union[bool, int, VerbosityLevel, None] = None) -> "BlockReader":
        """
        Open a SIMISA file and construct an appropriate BlockReader.

        This method inspects the SIMISA header to determine:
        - Compression (SIMISA@F = compressed, SIMISA@@ = uncompressed)
        - Encoding (UTF-16 LE via BOM, otherwise ASCII)
        - Format type (binary or text)
        - Token offset for binary blocks (based on subheader[5])

        It then returns either a `BinaryFileReader` or `TextFileReader` 
        configured to read the stream.

        Args:
            filepath (str): Path to a SIMISA file on disk.
            verbose: Optional verbosity level.

        Returns:
            BlockReader: Instance of `BinaryFileReader` or `TextFileReader`.

        Raises:
            TypeError: If `filepath` is not a string.
            SimisaHeaderError: If the file header is missing or unrecognized.
            SimisaSubheaderError: If the subheader is invalid or unsupported.
            UnresolvableIncludeError: If includes within the file cannot be resolved.
            OSError: If the file cannot be opened.
        """
        if not isinstance(filepath, str):
            raise TypeError(f"Parameter 'filepath' must be str, but got {type(filepath).__name__}")

        vlevel = normalize_verbosity(verbose)
        compressed = is_compressed(filepath, verbose=verbose)

        if compressed is None: # Header unknown, it is either missing, invalid or inside an include.
            first_include_path = peek_first_include(filepath)

            if first_include_path is None: # No include was present, therefore the header is missing or invalid.
                raise SimisaHeaderError(f"Unrecognized header in {filepath}")

            # Fallback path, resolve all includes to make sure the header can be found if inside an include.
            # Then use 'from_string' to re-do all checks and return the configured reader if a valid header was then found.
            with open(filepath, "rb") as f:
                bom = f.read(2)
                is_unicode = (bom == codecs.BOM_UTF16_LE)
                encoding = "utf-16-le" if is_unicode else "ascii"

                buffer = f.read()
                try:
                    text = buffer.decode(encoding)
                except UnicodeDecodeError:
                    raise SimisaHeaderError(f"Unrecognized header in {filepath}")

            text = resolve_includes(text, filepath, verbose=verbose)
            
            return BlockReader.from_string(text, verbose=verbose)

        # Found the beginning of a valid header in the file, proceed to read normally.
        verbose_print("reader", f"Opening SIMISA file '{filepath}' (compressed={compressed})", VerbosityLevel.NORMAL, vlevel)
        f = open(filepath, "rb")

        try:
            bom = f.read(2)
            is_unicode = (bom == codecs.BOM_UTF16_LE)
            encoding = "utf-16-le" if is_unicode else "ascii"

            if is_unicode:
                header_bytes = f.read(32)
                header = header_bytes[:16].decode(encoding)
            else:
                header_bytes = bom + f.read(14)
                header = header_bytes[:8].decode(encoding, errors="ignore")
            
            if compressed:
                stream = CompressedStreamReader(f)
            else:
                if header.startswith("\r\n"):
                    f.read(4 if is_unicode else 2)
                stream = f

            subheader_bytes = stream.read(32 if is_unicode else 16)
            subheader = subheader_bytes[:16 if is_unicode else 8].decode(encoding, errors="ignore")

            if len(subheader) < 8:
                raise SimisaSubheaderError(f"Subheader '{subheader}' too short in {filepath}")

            filetype = subheader[5]
            fileversion = int(subheader[6])
            fileformat = subheader[7]

            verbose_print(
                "reader",
                f"File '{filepath}' initialized: header='{header[:8]}', subheader='{subheader[:8]}', "
                f"filetype='{filetype}', fileversion={fileversion}, format='{'binary' if fileformat == 'b' else 'text'}'",
                VerbosityLevel.NORMAL,
                vlevel
            )

            if fileformat == "b":
                token_offset = 300 if filetype == "w" else 0
                return BinaryFileReader(stream, filepath, filetype, fileversion, token_offset, verbose=verbose)

            if fileformat != "t":
                raise SimisaSubheaderError(f"Unrecognized subheader '{subheader}' in {filepath}")

            text_stream = io.TextIOWrapper(stream, encoding=encoding)

            return TextFileReader(text_stream, filepath, filetype, fileversion, encoding, verbose=verbose)

        except Exception:
            f.close()
            raise

    @staticmethod
    def from_string(data: str, verbose: Union[bool, int, VerbosityLevel, None] = None) -> "BlockReader":
        """
        Construct a BlockReader from in-memory SIMISA text data.

        Unlike `open()`, this method only supports uncompressed text streams.
        Any includes must be resolved before calling this method.

        Args:
            data (str): Raw SIMISA text payload.
            verbose: Optional verbosity level.

        Returns:
            BlockReader: Instance of `TextFileReader` over the provided string data.

        Raises:
            TypeError: If `data` is not a string.
            SimisaHeaderError: If the string does not start with a recognized header.
            SimisaSubheaderError: If the subheader is missing, too short, or binary.
            UnresolvableIncludeError: If `data` contains unresolved includes.
        """
        if not isinstance(data, str):
            raise TypeError(f"Parameter 'data' must be str, but got {type(data).__name__}")

        vlevel = normalize_verbosity(verbose)
        data = data.lstrip("\ufeff\r\n\t ")

        if has_includes(data):
            raise UnresolvableIncludeError(
                "Includes are not supported with 'from_string', "
                "use the 'resolve_includes' function beforehand."
            )

        stream = io.StringIO(data)

        header = stream.read(16).lstrip("\r\n")

        if header.startswith("SIMISA@F"):
            raise SimisaHeaderError("Compressed data is not supported with 'from_string'")

        if not header.startswith("SIMISA@@"):
            raise SimisaHeaderError(f"Unrecognized header '{header}' in string input")

        subheader = stream.read(16)

        if len(subheader) < 8:
            raise SimisaSubheaderError(f"Subheader '{subheader}' too short in string input")

        filetype = subheader[5]
        fileversion = int(subheader[6])
        fileformat = subheader[7]

        if fileformat == "b":
            raise SimisaSubheaderError("Binary data is not supported with 'from_string'")

        if fileformat != "t":
            raise SimisaSubheaderError(f"Unrecognized subheader '{subheader}' in string input")

        verbose_print(
            "reader",
            f"String reader initialized: header='{header[:8]}', subheader='{subheader[:8]}', "
            f"filetype='{filetype}', fileversion={fileversion}",
            VerbosityLevel.NORMAL,
            vlevel
        )
        return TextFileReader(stream, "<string>", filetype, fileversion, "utf-8", verbose=verbose)

    def __iter__(self) -> Iterator["BlockReader"]:
        """
        Iterate over immediate child blocks.

        Returns:
            Iterator[BlockReader]
        """
        return self.sub_blocks()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    @contextmanager
    def sub_block(self, expected_id: Optional[TokenID] = None) -> Optional["BlockReader"]:
        """
        Context-scoped access to a single child block.

        Ensures block lifecycle correctness:
        - Optional ID validation on entry
        - Mandatory end-of-block validation on exit

        Args:
            expected_id: Expected TokenID for validation.

        Yields:
            BlockReader: Child block instance or None if there were no blocks.
        """
        sub_block = self.read_sub_block()

        if expected_id is not None and sub_block is not None:
            sub_block.verify_id(expected_id)

        try:
            yield sub_block
        finally:
            if sub_block is not None:
                sub_block.verify_end_of_block()
    
    def sub_blocks(self, expected_id: Optional[TokenID] = None) -> Iterator["BlockReader"]:
        """
        Iterate over all remaining child blocks.

        Guarantees:
        - Sequential consumption until `end_of_block()`
        - Each block is finalized via `verify_end_of_block()`

        Args:
            expected_id: Optional TokenID to validate each block.

        Yields:
            BlockReader: Child blocks.
        """
        while not self.end_of_block():
            sub_block = self.read_sub_block()

            if sub_block is None:
                continue

            if expected_id is not None:
                sub_block.verify_id(expected_id)
            
            try:
                yield sub_block
            finally:
                sub_block.verify_end_of_block()

    def verify_id(self, desired_id: TokenID) -> None:
        """
        Validate current block identifier.

        Emits warning on mismatch, does not raise.

        Args:
            desired_id: Expected TokenID.
        """
        if self.id != desired_id:
            logger.warning(
                f"Expected block '{desired_id.name}' (id {desired_id}), "
                f"but got '{self.id.name}' (id {self.id})"
            )
    
    def verify_count(self, expected: int, actual: int) -> None:
        """
        Validate element count consistency within a block.

        Emits warning if actual != expected, does not raise.

        Args:
            expected: Expected number of elements.
            actual: Observed number of elements.
        """
        block_name = self.id.name if self.id else "<unknown>"

        if actual < expected:
            logger.warning(
                f"Too few items in block '{block_name}', "
                f"read {actual} items but expected {expected}"
            )
        elif actual > expected:
            logger.warning(
                f"Too many items in block '{block_name}', "
                f"read {actual} items but expected {expected}"
            )

    def expect_comment(self) -> None:
        """
        Consume a comment block if present.

        Behavior:
        - If comment: skip silently
        - Else: log warning and skip current block
        """
        if self.id == TokenID.comment:
            self.skip()
        else:
            logger.warning(
                f"Expected comment block, "
                f"but got '{self.id.name}' (id {self.id})"
            )
            self.skip()

    @abstractmethod
    def read_sub_block(self) -> "BlockReader":
        pass

    @abstractmethod
    def skip(self) -> None:
        pass

    @abstractmethod
    def end_of_block(self) -> bool:
        pass

    @abstractmethod
    def verify_end_of_block(self) -> None:
        pass

    @abstractmethod
    def read_flags(self) -> int:
        pass

    @abstractmethod
    def read_int(self) -> int:
        pass

    @abstractmethod
    def read_uint(self) -> int:
        pass

    @abstractmethod
    def read_float(self) -> float:
        pass

    @abstractmethod
    def read_string(self) -> str:
        pass

    @abstractmethod
    def close(self):
        pass


class TextBlockReader(BlockReader):
    _TOKEN_TABLE: Dict[str, TokenID] = {
        name.lower(): token
        for name, token in TokenID.__members__.items()
    }

    def __init__(self, verbose: Union[bool, int, VerbosityLevel, None] = None):
        self.stf_reader: Optional[StfReader] = None
        self.id: Optional[TokenID] = None
        self.label: Optional[str] = None
        self.start_depth: int = 0
        self.at_end_of_block: bool = False
        self.is_closed: bool = False
        self.verbosity: VerbosityLevel = normalize_verbosity(verbose)

    def _get_token_id(self, token: str) -> TokenID:
        t = token.lower()

        token_id = self._TOKEN_TABLE.get(t)

        if token_id is not None:
            return token_id

        logger.warning(f"Skipped unknown token {token}")
        return TokenID.comment

    def read_sub_block(self) -> Optional[BlockReader]:
        sub_block = TextBlockReader(verbose=self.verbosity)
        sub_block.stf_reader = self.stf_reader

        token = self.stf_reader.read_item()

        if token == '':
            self.at_end_of_block = True
            return None

        if token == ')':
            self.at_end_of_block = True
            return None

        sub_block.id = self._get_token_id(token)

        token = self.stf_reader.read_item()

        if sub_block.id == TokenID.comment:
            sub_block.skip()
            return self.read_sub_block()

        if token == ')':
            self.at_end_of_block = True
            return None

        if token != '(':
            sub_block.label = token
            token = self.stf_reader.read_item()
            if token != '(':
                raise BlockReaderError(f"Expected '(' after label, but got '{token}'")

        sub_block.start_depth = self.stf_reader.depth
        verbose_print(
            "block",
            f"Reading text block: '{sub_block.id.name}' (id: {sub_block.id.value}, label: {sub_block.label})",
            VerbosityLevel.NORMAL,
            self.verbosity
        )
        return sub_block

    def skip(self):
        if self.at_end_of_block:
            return

        verbose_print("read", f"Skipping text block '{self.id.name if self.id else '<unknown>'}'", VerbosityLevel.DETAILED, self.verbosity)
        while not self.end_of_block():
            token = self.stf_reader.read_item()

            if token == '':
                logger.warning("Unexpected end of file")
                self.at_end_of_block = True
                return

        self.at_end_of_block = True

    def end_of_block(self) -> bool:
        if self.at_end_of_block:
            return True

        next_token = self.stf_reader.peek().value

        return (
            next_token == ')' and
            self.stf_reader.depth == self.start_depth
        )

    def verify_end_of_block(self):
        next_token = self.stf_reader.peek().value
        
        if next_token == '':
            return

        if next_token != ')':
            logger.warning(f"Expected end of block, but got '{self.stf_reader.peek().value}'")
        
        if next_token == ')':
            self.stf_reader.read_item()

        verbose_print("block", f"Verified end of text block '{self.id.name if self.id else '<root>'}'", VerbosityLevel.DETAILED, self.verbosity)

    def read_flags(self) -> int:
        val = self.stf_reader.read_hex(None)
        verbose_print("read", f"Read flags: 0x{val:X}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_int(self) -> int:
        val = self.stf_reader.read_int(None)
        verbose_print("read", f"Read int: {val}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_uint(self) -> int:
        val = self.stf_reader.read_uint(None)
        verbose_print("read", f"Read uint: {val}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_float(self) -> float:
        val = self.stf_reader.read_float(None)
        verbose_print("read", f"Read float: {val}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_string(self) -> str:
        val = self.stf_reader.read_item()
        verbose_print("read", f"Read string: '{val}'", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def close(self):
        if not self.is_closed:
            if self.stf_reader:
                self.stf_reader.close()
            self.is_closed = True


class TextFileReader(TextBlockReader):

    def __init__(
        self,
        stream: TextIO,
        filepath: str,
        filetype: str,
        fileversion: int,
        encoding: str,
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ):
        super().__init__(verbose=verbose)
        self.filepath = filepath
        self.filetype = filetype
        self.fileversion = fileversion
        self.encoding = encoding
        self.stream = stream
        self.is_closed = False
        self.at_end_of_block = False
        self.stf_reader = StfReader.from_stream(stream, filepath, verbose=self.verbosity)

    def skip(self):
        if self.is_closed:
            return

        self.stf_reader.close()
        self.is_closed = True
        self.at_end_of_block = True

    def verify_end_of_block(self):
        if self.is_closed:
            return

        token = self.stf_reader.read_item()

        if token != '':
            while token != '':
                if token != ')':
                    logger.warning(f"Expected end of file, but got '{token}' in {self.filepath}")
                    return

                token = self.stf_reader.read_item()

    def end_of_block(self) -> bool:
        if self.is_closed or self.at_end_of_block:
            return True

        return self.stf_reader.eof()

    def close(self):
        if not self.is_closed:
            if self.stf_reader:
                self.stf_reader.close()
            self.is_closed = True


class BinaryBlockReader(BlockReader):
    _UINT32 = struct.Struct("<I")
    _INT32 = struct.Struct("<i")
    _UINT16 = struct.Struct("<H")
    _FLOAT32 = struct.Struct("<f")
    _BLOCK_HEADER = struct.Struct("<HHI")

    def __init__(self, verbose: Union[bool, int, VerbosityLevel, None] = None):
        self.filepath: str = ""
        self.stream: Optional[BinaryIO] = None
        self.token_offset: int = 0
        self.remaining_bytes: int = 0
        self.id: Optional[TokenID] = None
        self.flags: int = 0
        self.label: Optional[str] = None
        self._buffer: Optional[bytes] = None
        self.verbosity: VerbosityLevel = normalize_verbosity(verbose)

    def _read(self, num_bytes: int) -> bytes:
        if self.stream is None:
            raise RuntimeError("Stream is not initialized")

        if num_bytes == 0:
            return b""
        
        if self._buffer is not None:
            data = self._buffer
            self._buffer = None

            if num_bytes > 1:
                data += self.stream.read(num_bytes - 1)
        else:
            data = self.stream.read(num_bytes)

        if len(data) != num_bytes:
            raise BlockReaderError("Unexpected EOF in block")

        self.remaining_bytes -= num_bytes
        return data

    def read_sub_block(self) -> Optional[BlockReader]:
        if self.stream is None:
            raise RuntimeError("Stream is not initialized")

        if self.remaining_bytes < 8:
            raise BlockReaderError("Not enough bytes for sub-block header")

        raw_id, raw_flags, size = self._BLOCK_HEADER.unpack(self._read(8))

        sub_block = BinaryBlockReader(verbose=self.verbosity)
        sub_block.stream = self.stream
        sub_block.filepath = self.filepath
        sub_block.token_offset = self.token_offset
        sub_block.filetype = self.filetype
        sub_block.fileversion = self.fileversion

        sub_block.flags = raw_flags
        sub_block.remaining_bytes = size

        self.remaining_bytes -= size

        token_id = raw_id + self.token_offset

        try:
            sub_block.id = TokenID(token_id)
        except ValueError:
            logger.warning(f"Unknown Token ID {token_id}, skipping block.")
            sub_block.skip()
            return self.read_sub_block()

        if sub_block.remaining_bytes > 0:
            label_length = sub_block._read(1)[0]

            if label_length > 0:
                raw_label = sub_block._read(label_length * 2)
                sub_block.label = raw_label.decode("utf-16-le")

        verbose_print(
            "block",
            f"Reading binary block: '{sub_block.id.name}' (id: {token_id}, size: {size}, flags: 0x{raw_flags:04X}, label: {sub_block.label})",
            VerbosityLevel.NORMAL,
            self.verbosity
        )
        return sub_block

    def read_flags(self) -> int:
        val = self._UINT32.unpack(self._read(4))[0]
        verbose_print("read", f"Read flags: 0x{val:X}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_int(self) -> int:
        val = self._INT32.unpack(self._read(4))[0]
        verbose_print("read", f"Read int: {val}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_uint(self) -> int:
        val = self._UINT32.unpack(self._read(4))[0]
        verbose_print("read", f"Read uint: {val}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_float(self) -> float:
        val = self._FLOAT32.unpack(self._read(4))[0]
        verbose_print("read", f"Read float: {val}", VerbosityLevel.DEBUG, self.verbosity)
        return val

    def read_string(self) -> str:
        length = self._UINT16.unpack(self._read(2))[0]

        if length == 0:
            val = ""
        else:
            raw_string = self._read(length * 2)
            val = raw_string.decode("utf-16-le")
        verbose_print("read", f"Read string: '{val}'", VerbosityLevel.DEBUG, self.verbosity)
        return val
    
    def skip(self):
        if self.remaining_bytes <= 0:
            return

        if self.stream is None:
            return

        verbose_print("read", f"Skipping binary block '{self.id.name if self.id else '<unknown>'}' ({self.remaining_bytes} bytes)", VerbosityLevel.DETAILED, self.verbosity)
        skipped_bytes = self.stream.read(self.remaining_bytes)

        if self.remaining_bytes <= 1000:
            logger.warning(f"Skipped data: {skipped_bytes.hex().upper()}")
        else:
            logger.warning(f"Length of skipped data: {len(skipped_bytes)}")

        self.remaining_bytes = 0

    def end_of_block(self) -> bool:
        return self.remaining_bytes == 0

    def verify_end_of_block(self):
        if not self.end_of_block():
            logger.warning(
                f"Expected end of block '{self.id.name}' (id {self.id}), "
                f"but got extra data"
            )
            self.skip()
        verbose_print("block", f"Verified end of binary block '{self.id.name if self.id else '<root>'}'", VerbosityLevel.DETAILED, self.verbosity)

    def close(self):
        if self.stream:
            self.stream.close()
            self.stream = None


class BinaryFileReader(BinaryBlockReader):

    def __init__(
        self,
        stream: BinaryIO,
        filepath: str,
        filetype: str,
        fileversion: int,
        token_offset: int,
        verbose: Union[bool, int, VerbosityLevel, None] = None
    ):
        super().__init__(verbose=verbose)
        self.filepath = filepath
        self.stream = stream
        self.filetype = filetype
        self.fileversion = fileversion
        self.token_offset = token_offset
        self.remaining_bytes = float("inf")

    def skip(self):
        if self.stream is None:
            return

        while True:
            chunk = self.stream.read(65536)
            if not chunk:
                break

        self.remaining_bytes = 0
    
    def end_of_block(self) -> bool:
        if self.stream is None:
            return True

        if self._buffer is not None:
            return False

        self._buffer = self.stream.read(1)

        return self._buffer == b""
    
    def verify_end_of_block(self):
        if not self.end_of_block():
            logger.warning(
                f"Expected end of file, but got extra data in {self.filepath}"
            )

    def close(self):
        if self.stream:
            self.stream.close()

