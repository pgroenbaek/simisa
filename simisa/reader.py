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
import os
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
from .progress import ProgressReporter, ProgressCallback
from .verbosity import Verbose, normalize_verbosity, verbosity_enabled

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
        self._position = 0

    def readable(self):
        return True
    
    def seekable(self):
        return False

    def tell(self):
        return self._position
    
    @property
    def closed(self):
        return self.fileobj is None

    def read(self, size=-1):
        if size == 0:
            return b""

        if self._eof and not self._buffer:
            return b""

        if size is None or size < 0:
            data = self._read_all()
        else:
            data = self._read_exact(size)

        self._position += len(data)
        
        return data

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
    def open(filepath: str, progress: ProgressCallback = None, verbose: Verbose = None) -> "BlockReader":
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
            progress (ProgressCallback, optional): Callback for receiving progress updates.
            verbose (Verbose, optional): Verbosity level for logging.

        Returns:
            BlockReader: Instance of `BinaryFileReader` or `TextFileReader`.

        Raises:
            TypeError: If a parameter is not of the expected type.
            SimisaHeaderError: If the file header is missing or unrecognized.
            SimisaSubheaderError: If the subheader is invalid or unsupported.
            UnresolvableIncludeError: If includes within the file cannot be resolved.
            OSError: If the file cannot be opened.
        """
        if not isinstance(filepath, str):
            raise TypeError(f"Parameter 'filepath' must be str, but got {type(filepath).__name__}")

        progress = ProgressReporter(progress)
        verbose = normalize_verbosity(verbose)

        total_size = os.path.getsize(filepath)
        compressed = is_compressed(filepath, verbose=verbose)

        if compressed is None: # Header unknown, it is either missing, invalid or inside an include.
            if verbosity_enabled(verbose, logging.INFO):
                logger.info(
                    "No valid SIMISA header found in '%s' (compressed=%s), proceeding to check for an include.",
                    filepath,
                    compressed
                )
            
            first_include_path = peek_first_include(filepath)

            if first_include_path is None: # No include was present, therefore the header is missing or invalid.
                if verbosity_enabled(verbose, logging.INFO):
                    logger.info(
                        "No include found include at the start of file '%s', so the header is missing or invalid.",
                        filepath,
                        compressed
                    )
                
                raise SimisaHeaderError(f"Unrecognized header in {filepath}")

            # Fallback path, try to resolve all includes to make sure the header can be found if inside an include.
            # Then use 'from_string' to re-do all checks and return the configured reader if a valid header was found.
            if verbosity_enabled(verbose, logging.INFO):
                logger.info(
                    "Found an include at the start of file '%s', proceeding to resolve the include tree and check for a header again.",
                    filepath,
                    compressed
                )

            with open(filepath, "rb") as f:
                bom = f.read(2)
                has_utf16le_bom = (bom == codecs.BOM_UTF16_LE)
                encoding = "utf-16-le" if has_utf16le_bom else "ascii"

                buffer = f.read()
                try:
                    text = buffer.decode(encoding)
                except UnicodeDecodeError:
                    raise SimisaHeaderError(f"Unrecognized header in {filepath}")

            text = resolve_includes(text, filepath, verbose=verbose)
            
            return BlockReader.from_string(text, verbose=verbose)

        # Found the beginning of a valid header in the file, proceed to read normally.
        if verbosity_enabled(verbose, logging.INFO):
            logger.info(
                "Found a valid SIMISA header in '%s' (compressed=%s), proceeding to read normally.",
                filepath,
                compressed
            )

        f = open(filepath, "rb")

        try:
            bom = f.read(2)
            has_utf16le_bom = (bom == codecs.BOM_UTF16_LE)
            encoding = "utf-16-le" if has_utf16le_bom else "ascii"

            if has_utf16le_bom:
                header_bytes = f.read(32)
                header = header_bytes[:16].decode(encoding)
            else:
                header_bytes = bom + f.read(14)
                header = header_bytes[:8].decode(encoding, errors="ignore")
            
            if compressed:
                size_position = 18 if has_utf16le_bom else 8
                total_size = int.from_bytes(
                    header_bytes[size_position:size_position + 4],
                    "little",
                )
                stream = CompressedStreamReader(f)
            else:
                if header.startswith("\r\n"):
                    f.read(4 if has_utf16le_bom else 2)
                stream = f

            subheader_bytes = stream.read(32 if has_utf16le_bom else 16)
            subheader = subheader_bytes[:16 if has_utf16le_bom else 8].decode(encoding, errors="ignore")

            if len(subheader) < 8:
                raise SimisaSubheaderError(f"Subheader '{subheader}' too short in {filepath}")

            if verbosity_enabled(verbose, logging.INFO):
                logger.info(
                    "File '%s' header read (header='%s', subheader='%s')",
                    filepath,
                    header,
                    subheader
                )

            filetype = subheader[5]
            fileversion = int(subheader[6])
            fileformat = subheader[7]

            progress.total(total_size)

            if fileformat == "b":
                token_offset = 300 if filetype == "w" else 0

                if verbosity_enabled(verbose, logging.INFO):
                    logger.info(
                        "Creating binary reader with config (filetype='%s', fileversion='%s', token_offset=%d)",
                        filetype,
                        fileversion,
                        token_offset,
                    )
                
                return BinaryFileReader(
                    stream,
                    filepath,
                    filetype,
                    fileversion,
                    token_offset,
                    progress,
                    verbose=verbose
                )

            if fileformat != "t":
                raise SimisaSubheaderError(f"Unrecognized subheader '{subheader}' in {filepath}")

            text_stream = io.TextIOWrapper(stream, encoding=encoding)

            if verbosity_enabled(verbose, logging.INFO):
                logger.info(
                    "Creating text reader with config (filetype='%s', fileversion='%s', encoding='%s')",
                    filetype,
                    fileversion,
                    encoding,
                )

            return TextFileReader(
                text_stream,
                filepath,
                filetype,
                fileversion,
                encoding,
                progress,
                verbose=verbose
            )

        except Exception:
            f.close()
            raise

    @staticmethod
    def from_string(text_data: str, progress: ProgressCallback = None, verbose: Verbose = None) -> "BlockReader":
        """
        Construct a BlockReader from in-memory SIMISA text data.

        Unlike `open()`, this method only supports uncompressed text streams.
        Any includes must be resolved before calling this method.

        Args:
            text_data (str): Raw SIMISA text payload.
            progress (ProgressCallback, optional): Callback for receiving progress updates.
            verbose (Verbose, optional): Verbosity level for logging.

        Returns:
            BlockReader: Instance of `TextFileReader` over the provided string data.

        Raises:
            TypeError: If a parameter is not of the expected type.
            SimisaHeaderError: If the string does not start with a recognized header.
            SimisaSubheaderError: If the subheader is missing, too short, or binary.
            UnresolvableIncludeError: If `text_data` contains unresolved includes.
        """
        if not isinstance(text_data, str):
            raise TypeError(f"Parameter 'text_data' must be str, but got {type(text_data).__name__}")

        progress = ProgressReporter(progress)
        verbose = normalize_verbosity(verbose)

        text_data = text_data.lstrip("\ufeff\r\n\t ")

        if has_includes(text_data):
            raise UnresolvableIncludeError(
                "Includes are not supported with 'from_string', "
                "use the 'resolve_includes' function beforehand."
            )

        stream = io.StringIO(text_data)

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

        if verbosity_enabled(verbose, logging.INFO):
            logger.info(
                "Creating text reader with config (filetype='%s', fileversion='%s', encoding='utf-8')",
                filetype,
                fileversion,
            )
        
        progress.total(len(text_data))

        return TextFileReader(
            stream,
            "<string>",
            filetype,
            fileversion,
            "utf-8",
            progress,
            verbose=verbose
        )

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
    def report_progress(self, message: str) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class TextBlockReader(BlockReader):
    _TOKEN_TABLE: Dict[str, TokenID] = {
        name.lower(): token
        for name, token in TokenID.__members__.items()
    }

    def __init__(
        self,
        stf_reader: StfReader,
        parent: Optional["TextBlockReader"] = None,
        id: Optional[TokenID] = None,
        label: Optional[str] = None,
        verbose: Verbose = None
    ):
        self.stf_reader = stf_reader
        self.parent = parent
        self.id = id
        self.label = label
        self.verbose: Optional[int] = normalize_verbosity(verbose)
        self.start_depth: int = 0
        self.at_end_of_block: bool = False
        self.is_closed: bool = False

    def _get_token_id(self, token: str) -> TokenID:
        t = token.lower()

        token_id = self._TOKEN_TABLE.get(t)

        if token_id is not None:
            return token_id

        logger.warning(f"Skipped unknown token {token}")

        return TokenID.comment

    def read_sub_block(self) -> Optional[BlockReader]:
        sub_block = TextBlockReader(
            self.stf_reader,
            parent=self,
            verbose=self.verbose
        )

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

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Reading text block: '%s' (id: %d, label: %s)",
                sub_block.id.name,
                sub_block.id.value,
                sub_block.label,
            )

        return sub_block

    def skip(self) -> None:
        if self.at_end_of_block:
            return

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Skipping remaining data in text block '%s'",
                self.id.name if self.id else '<unknown>',
            )

        skipped_tokens = []

        while not self.end_of_block():
            token = self.stf_reader.read_item()

            if token == "":
                logger.warning("Unexpected end of file")

                self.at_end_of_block = True
                return

            skipped_tokens.append(token)

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug(
                "Skipped data in text block '%s': %r",
                self.id.name if self.id else "<unknown>",
                skipped_tokens,
            )
        
        self.at_end_of_block = True

    def end_of_block(self) -> bool:
        if self.at_end_of_block:
            return True

        next_token = self.stf_reader.peek().value

        return (
            next_token == ')' and
            self.stf_reader.depth == self.start_depth
        )

    def verify_end_of_block(self) -> None:
        next_token = self.stf_reader.peek().value
        
        if next_token == '':
            return

        if next_token != ')':
            logger.warning(f"Expected end of block, but got '{self.stf_reader.peek().value}'")
        
        if next_token == ')':
            self.stf_reader.read_item()

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Verified end of text block '%s'",
                self.id.name if self.id else '<root>',
            )

    def read_flags(self) -> int:
        value = self.stf_reader.read_hex(None)

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read flags: 0x%X", value)
        
        return value

    def read_int(self) -> int:
        value = self.stf_reader.read_int(None)

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read int: %d", value)
        
        return value

    def read_uint(self) -> int:
        value = self.stf_reader.read_uint(None)

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read uint: %d", value)

        return value

    def read_float(self) -> float:
        value = self.stf_reader.read_float(None)

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read float: %s", value)

        return value

    def read_string(self) -> str:
        value = self.stf_reader.read_item()

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read string: %r", value)

        return value
    
    def report_progress(self, message: str) -> None:
        if self.parent is not None:
            self.parent.report_progress(message)

    def close(self) -> None:
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
        progress: ProgressReporter,
        verbose: Verbose = None
    ):
        super().__init__(
            StfReader.from_stream(stream, filepath, verbose=verbose),
            verbose=verbose
        )
        self.stream = stream
        self.filepath = filepath
        self.filetype = filetype
        self.fileversion = fileversion
        self.encoding = encoding
        self.progress = progress
        self.is_closed = False
        self.at_end_of_block = False

    def skip(self) -> None:
        if self.is_closed:
            return

        self.stf_reader.close()
        self.is_closed = True
        self.at_end_of_block = True

    def verify_end_of_block(self) -> None:
        if self.is_closed:
            return

        token = self.stf_reader.read_item()

        if token != '':
            while token != '':
                if token != ')':
                    logger.warning(f"Expected end of file, but got '{token}' in {self.filepath}")
                    return

                token = self.stf_reader.read_item()
        
        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Verified end of text block '%s'",
                self.id.name if self.id else '<root>',
            )

    def end_of_block(self) -> bool:
        if self.is_closed or self.at_end_of_block:
            return True

        return self.stf_reader.eof()
    
    def report_progress(self, message: str) -> None:
        current = self.stf_reader.chars_read
        is_utf16le = self.encoding in ("utf-16-le", "UTF-16-LE")

        if is_utf16le:
            current *= 2

        self.progress.update(message, current)

    def close(self) -> None:
        if not self.is_closed:

            if self.stf_reader:
                self.stf_reader.close()
            
            self.is_closed = True
        
        self.progress.complete()

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info("Closed reader for '%s'", self.filepath)


class BinaryBlockReader(BlockReader):
    _UINT32 = struct.Struct("<I")
    _INT32 = struct.Struct("<i")
    _UINT16 = struct.Struct("<H")
    _FLOAT32 = struct.Struct("<f")
    _BLOCK_HEADER = struct.Struct("<HHI")

    def __init__(
        self,
        stream: BinaryIO,
        parent: Optional["BinaryBlockReader"] = None,
        id: Optional[TokenID] = None,
        label: Optional[str] = None,
        flags: int = 0,
        token_offset: int = 0,
        verbose: Verbose = None
    ):
        self.stream = stream
        self.parent = parent
        self.id = id
        self.label = label
        self.flags = flags
        self.token_offset = token_offset
        self.verbose: Optional[int] = normalize_verbosity(verbose)
        self.remaining_bytes: int = 0
        self._buffer: Optional[bytes] = None

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

        sub_block = BinaryBlockReader(
            self.stream,
            parent=self,
            token_offset=self.token_offset,
            verbose=self.verbose
        )

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

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Reading binary block: '%s' (id: %d, size: %d, flags: 0x%04X, label: %s)",
                sub_block.id.name,
                sub_block.id.value,
                size,
                raw_flags,
                sub_block.label,
            )

        return sub_block

    def read_flags(self) -> int:
        value = self._UINT32.unpack(self._read(4))[0]

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read flags: 0x%X", value)
        
        return value

    def read_int(self) -> int:
        value = self._INT32.unpack(self._read(4))[0]

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read int: %d", value)
        
        return value

    def read_uint(self) -> int:
        value = self._UINT32.unpack(self._read(4))[0]

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read uint: %d", value)
        
        return value

    def read_float(self) -> float:
        value = self._FLOAT32.unpack(self._read(4))[0]

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read float: %s", value)
        
        return value

    def read_string(self) -> str:
        length = self._UINT16.unpack(self._read(2))[0]

        if length == 0:
            value = ""
        else:
            raw_string = self._read(length * 2)
            value = raw_string.decode("utf-16-le")

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug("Read string: %r", value)

        return value
    
    def skip(self) -> None:
        if self.remaining_bytes <= 0:
            return

        if self.stream is None:
            return

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Skipping remaining data in binary block '%s' (%d bytes)",
                self.id.name if self.id else "<unknown>",
                self.remaining_bytes,
            )

        skipped_bytes = self.stream.read(self.remaining_bytes)

        if verbosity_enabled(self.verbose, logging.DEBUG):
            logger.debug(
                "Skipped data in binary block '%s': %s",
                self.id.name if self.id else "<unknown>",
                skipped_bytes.hex().upper(),
            )
        
        self.remaining_bytes = 0

    def end_of_block(self) -> bool:
        return self.remaining_bytes == 0

    def verify_end_of_block(self) -> None:
        if not self.end_of_block():
            logger.warning(
                f"Expected end of block '{self.id.name}' (id {self.id}), "
                f"but got extra data"
            )
            self.skip()

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Verified end of binary block '%s'",
                self.id.name if self.id else '<root>',
            )
    
    def report_progress(self, message: str) -> None:
        if self.parent is not None:
            self.parent.report_progress(message)
    
    def close(self) -> None:
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
        progress: ProgressReporter,
        verbose: Verbose = None
    ):
        super().__init__(
            stream,
            token_offset=token_offset,
            verbose=verbose
        )
        self.filepath = filepath
        self.filetype = filetype
        self.fileversion = fileversion
        self.progress = progress
        self.remaining_bytes = float("inf")

    def skip(self) -> None:
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
    
    def verify_end_of_block(self) -> None:
        if not self.end_of_block():
            logger.warning(
                f"Expected end of file, but got extra data in {self.filepath}"
            )

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info(
                "Verified end of binary block '%s'",
                self.id.name if self.id else '<root>',
            )
    
    def report_progress(self, message: str) -> None:
        current = self.stream.tell()

        self.progress.update(message, current)

    def close(self) -> None:
        if self.stream:
            self.stream.close()
        
        self.progress.complete()

        if verbosity_enabled(self.verbose, logging.INFO):
            logger.info("Closed reader for '%s'", self.filepath)

