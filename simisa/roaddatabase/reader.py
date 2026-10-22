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
from ..reader import BlockReader
from ..header import SimisaSubheaderError
from ..progress import ProgressCallback
from ..verbosity import Verbose
from ..trackdatabase.reader import read_track_nodes, read_tr_item_table
from .models import RoadDB



def load(
    filepath: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> RoadDB:
    """
    Load and parse a road database file from disk.

    This function opens the file at the given path, validates that it is a supported rdb
    file based on its subheader, and returns a parsed `RoadDB` object.

    Args:
        filepath (str): Path to the rdb file.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        RoadDB: The parsed road database object.

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

        if not reader.filetype == 'T':
            raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a road database?")

        return read_roaddb(reader)


def loads(
    rdb_text: str,
    progress: ProgressCallback = None,
    verbose: Verbose = None
) -> RoadDB:
    """
    Parse a road database from a string containing rdb data.

    This function does not support binary or compressed data. It reads rdb
    data from the provided string, validates that it represents a supported
    road database file based on its subheader, and returns a parsed `RoadDB` object.

    Args:
        rdb_text (str): String containing rdb file data.
        verbose (Verbose, optional): Verbosity level for logging.

    Returns:
        RoadDB: The parsed road database object.

    Raises:
        TypeError: If a parameter is not of the expected type.
        SimisaHeaderError: If the data has an invalid or unrecognized SIMISA header.
        SimisaSubheaderError: If the data has an invalid or unrecognized SIMISA subheader.
        BlockReaderError: If the block reader encounters an error or malformed data.
        StfReaderError: If the STF reader encounters an error or malformed data.
        UnresolvableIncludeError: If includes within the file cannot be resolved.
    """
    if not isinstance(rdb_text, str):
        raise TypeError(f"Parameter 'rdb_text' must be str, but got {type(rdb_text).__name__}")

    reader = BlockReader.from_string(rdb_text, progress=progress, verbose=verbose)

    if not reader.filetype == 'T':
        raise SimisaSubheaderError(f"Unrecognized filetype '{reader.filetype}' in subheader. Is it a road database?")

    return read_roaddb(reader)


def read_roaddb(reader: BlockReader) -> RoadDB:
    """
    Read and parse a road database from a BlockReader.

    Consumes the `TrackDB` block and its child blocks, returning a RoadDB object.

    Args:
        reader (BlockReader): Reader positioned at the start of a road database file.

    Returns:
        RoadDB: The parsed road database.
    """
    with reader.sub_block(TokenID.TrackDB) as trackdb_block:
        serial = 0

        with trackdb_block.sub_block(TokenID.Serial) as serial_block:
            serial = serial_block.read_uint()

        track_nodes = read_track_nodes(trackdb_block)
        tr_item_table = read_tr_item_table(trackdb_block)

        return RoadDB(
            serial=serial,
            track_nodes=track_nodes,
            tr_item_table=tr_item_table
        )
