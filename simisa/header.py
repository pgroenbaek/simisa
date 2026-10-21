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

import codecs
import logging
from typing import Optional, Union

from .verbosity import Verbose, normalize_verbosity, verbosity_enabled

logger = logging.getLogger(__name__)


class SimisaHeaderError(Exception):
    """Raised when a SIMISA header is missing or invalid."""
    pass


class SimisaSubheaderError(Exception):
    """Raised when a SIMISA subheader is missing or invalid."""
    pass


def is_utf16le(filepath: str, verbose: Verbose = None) -> Optional[bool]:
    """
    Checks whether a file is encoded in UTF-16 LE based on its BOM.

    The function reads the first two bytes of the file and determines
    whether they match the UTF-16 LE byte order mark.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        True if the file is UTF-16 LE encoded, otherwise False.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )

    verbose = normalize_verbosity(verbose)

    with open(filepath, "rb") as f:
        bom = f.read(2)
        has_utf16le_bom = (bom == codecs.BOM_UTF16_LE)

        if verbosity_enabled(verbose, logging.DEBUG):
            logger.debug(
                "File '%s' (has_utf16le_bom=%s)",
                filepath,
                has_utf16le_bom,
            )

        return has_utf16le_bom


def peek_header(filepath: str, verbose: Verbose = None) -> Optional[str]:
    """
    Reads the beginning of a file and extracts the SIMISA header if present.

    The function detects whether the file is UTF-16 LE encoded via BOM,
    decodes an initial portion of the file accordingly, and checks whether
    the resulting text starts with a known valid SIMISA header.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        The detected header string if it starts with a valid SIMISA header,
        otherwise None.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )
    
    verbose = normalize_verbosity(verbose)

    with open(filepath, "rb") as f:
        bom = f.read(2)
        has_utf16le_bom = (bom == codecs.BOM_UTF16_LE)

        if has_utf16le_bom:
            buffer = f.read(32)
            header = buffer.decode("utf-16-le")
        else:
            buffer = bom + f.read(14)
            header = buffer.decode("ascii", errors="ignore")

        header = header.lstrip("\r\n")

        valid_headers = [
            "SIMISA@@",
            "SIMISA@F",
        ]

        if not any(header.startswith(h) for h in valid_headers):
            if verbosity_enabled(verbose, logging.DEBUG):
                logger.debug(
                    "No valid SIMISA header in '%s', got '%s'",
                    filepath,
                    header,
                )
            
            return None
        
        if verbosity_enabled(verbose, logging.INFO):
            logger.info(
                "Header in '%s': '%s' (has_utf16le_bom=%s)",
                filepath,
                header[:8],
                has_utf16le_bom,
            )
        
        return header


def is_compressed(filepath: str, verbose: Verbose = None) -> Optional[bool]:
    """
    Determines whether a file is compressed based on its SIMISA header.

    This function reads the file header using `peek_header` and infers
    compression from known SIMISA header markers.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        True if the file is compressed,
        False if it is uncompressed,
        None if the header is missing or unrecognized.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )
    
    verbose = normalize_verbosity(verbose)

    header = peek_header(filepath, verbose=verbose)

    if header is None:
        return None

    elif header.startswith("SIMISA@F"):
        if verbosity_enabled(verbose, logging.INFO):
            logger.info(
                "File '%s' is compressed (SIMISA@F)",
                filepath,
            )
        
        return True

    elif header.startswith("SIMISA@@"):
        if verbosity_enabled(verbose, logging.INFO):
            logger.info(
                "File '%s' is uncompressed (SIMISA@@)",
                filepath,
            )
        
        return False

    return None


def peek_subheader(filepath: str, verbose: Verbose = None) -> Optional[str]:
    """
    Reads and extracts a SIMISA subheader from a file.

    The function determines whether the file is compressed and/or UTF-16 LE encoded,
    then processes the stream accordingly. For compressed files, it decompresses
    the payload using zlib before reading the subheader. For uncompressed files,
    it reads directly from the file stream, accounting for potential newline prefixes.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        The decoded subheader string if successfully read and valid,
        otherwise None.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )
    
    verbose = normalize_verbosity(verbose)

    compressed = is_compressed(filepath, verbose=verbose)

    if compressed is None:
        return None

    with open(filepath, "rb") as f:
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
            from .reader import CompressedStreamReader
            stream = CompressedStreamReader(f)
        else:
            if header.startswith("\r\n"):
                f.read(4 if has_utf16le_bom else 2)
            stream = f

        try:
            subheader_bytes = stream.read(32 if has_utf16le_bom else 16)
            subheader = subheader_bytes[:16 if has_utf16le_bom else 8].decode(encoding, errors="ignore")

            if len(subheader) < 8:
                if verbosity_enabled(verbose, logging.DEBUG):
                    logger.debug(
                        "Subheader in '%s' too short (<8 bytes)",
                        filepath,
                    )
                
                return None

            if verbosity_enabled(verbose, logging.INFO):
                logger.info(
                    "Subheader in '%s': '%s' (filetype='%s', fileversion=%s, fileformat='%s')",
                    filepath,
                    subheader[:8],
                    subheader[5],
                    subheader[6],
                    subheader[7],
                )
            
            return subheader
            
        finally:
            if stream is not f:
                stream.close()


def is_binary(filepath: str, verbose: Verbose = None) -> Optional[bool]:
    """
    Determines whether a file is in binary format based on its SIMISA subheader.

    The function reads the subheader using `peek_subheader` and inspects
    the format indicator character to determine if the file is binary.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        True if the file is identified as binary,
        False if it is not binary,
        None if the subheader is missing or invalid.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )
    
    verbose = normalize_verbosity(verbose)

    subheader = peek_subheader(filepath, verbose=verbose)

    if subheader is None:
        return None

    if len(subheader) < 8:
        return None

    fileformat = subheader[7]

    is_binary_format = (fileformat == "b")

    if verbosity_enabled(verbose, logging.DEBUG):
        logger.debug(
            "File '%s' (is_binary_format=%s)",
            filepath,
            is_binary_format
        )
        
    return is_binary_format


def is_text(filepath: str, verbose: Verbose = None) -> Optional[bool]:
    """
    Determines whether a file is in text format based on its SIMISA subheader.

    The function reads the subheader using `peek_subheader` and inspects
    the format indicator character to determine if the file is text-based.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        True if the file is identified as text,
        False if it is not text,
        None if the subheader is missing or invalid.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )
    
    verbose = normalize_verbosity(verbose)

    subheader = peek_subheader(filepath, verbose=verbose)

    if subheader is None:
        return None

    if len(subheader) < 8:
        return None

    fileformat = subheader[7]

    is_text_format = (fileformat == "t")

    if verbosity_enabled(verbose, logging.DEBUG):
        logger.debug(
            "File '%s' (is_text_format=%s)",
            filepath,
            is_text_format
        )
        
    return is_text_format


def read_filetype(filepath: str, verbose: Verbose = None) -> Optional[str]:
    """
    Extracts the file type identifier from a SIMISA file subheader.

    The function reads the subheader using `peek_subheader` and returns
    the character representing the file type.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        A single-character string representing the file type,
        or None if the subheader is missing or invalid.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )
    
    verbose = normalize_verbosity(verbose)

    subheader = peek_subheader(filepath, verbose=verbose)

    if subheader is None:
        return None

    if len(subheader) < 8:
        return None

    filetype = subheader[5]

    if verbosity_enabled(verbose, logging.DEBUG):
        logger.debug(
            "File '%s' (filetype=%s)",
            filepath,
            filetype
        )
    
    return filetype


def read_fileversion(filepath: str, verbose: Verbose = None) -> Optional[int]:
    """
    Extracts the file version number from a SIMISA file subheader.

    The function reads the subheader using `peek_subheader` and parses
    the version character as an integer.

    Args:
        filepath (str): Path to the file to inspect.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        An integer representing the file version,
        or None if the subheader is missing, invalid, or cannot be parsed.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )

    verbose = normalize_verbosity(verbose)

    subheader = peek_subheader(filepath, verbose=verbose)

    if subheader is None:
        return None

    if len(subheader) < 8:
        return None

    fileversion = int(subheader[6])

    if verbosity_enabled(verbose, logging.DEBUG):
        logger.debug(
            "File '%s' (fileversion=%s)",
            filepath,
            fileversion
        )
    
    return fileversion