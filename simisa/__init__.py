"""
Simisa

A Python module to read and write files used with MSTS and Open Rails.

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

__version__ = '0.1.0b0'
__all__ = [
    'is_unicode', 'peek_header', 'peek_subheader',
    'is_compressed', 'is_binary', 'is_text',
    'read_filetype', 'read_fileversion',
    'SimisaHeaderError', 'SimisaSubheaderError',
    'has_includes', 'peek_first_include',
    'resolve_include', 'resolve_includes',
    'UnresolvableIncludeError',
    'TokenID', 'Units', 'StfReader',
    'BlockReader', 'BlockWriter', 'BlockFormat',
    'BlockReaderError', 'BlockWriterError',
    'StfReaderError',
    'VerbosityLevel', 'normalize_verbosity', 'get_global_verbosity',
    'set_global_verbosity', 'set_verbose_output',
    'verbose_print',
    'roaddatabase', 'rdb',
    'shape', 's', 'terrain', 't',
    'tracksections', 'tsection',
    'trackdatabase', 'tdb',
    'world', 'w'
]

__author__ = 'Peter Grønbæk Andersen <peter@grnbk.io>'

from .header import is_unicode, peek_header, peek_subheader
from .header import is_compressed, is_binary, is_text
from .header import read_filetype, read_fileversion
from .header import SimisaHeaderError, SimisaSubheaderError
from .include import has_includes, peek_first_include
from .include import resolve_include, resolve_includes
from .include import UnresolvableIncludeError
from .token_id import TokenID
from .units import Units
from .stf import StfReader, StfReaderError
from .reader import BlockReader, BlockReaderError
from .writer import BlockWriter, BlockWriterError
from .format import BlockFormat
from .verbose import (
    VerbosityLevel, normalize_verbosity, get_global_verbosity,
    set_global_verbosity, set_verbose_output,
    verbose_print
)

from . import roaddatabase
from . import roaddatabase as rdb
from . import shape
from . import shape as s
from . import terrain
from . import terrain as t
from . import trackdatabase
from . import trackdatabase as tdb
from . import tracksections
from . import tracksections as tsection
from . import world
from . import world as w
