"""
This file is part of Simisa.

This code is loosely based on `STFReader.cs` from the `Orts.Parsers.Msts`
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
import logging
from dataclasses import dataclass
from typing import Optional, Union

from .include import resolve_include
from .units import Units
from .verbose import VerbosityLevel, normalize_verbosity, verbose_print

logger = logging.getLogger(__name__)

# TODO Handle units


class StfReaderError(Exception):
    """Raised when an STF reader encounters an error or malformed data."""
    pass


class StfToken:
    __slots__ = ("kind", "value")

    def __init__(self, kind, value):
        self.kind = kind
        self.value = value

    @property
    def is_eof(self):
        return self.kind == "eof"

    @property
    def is_block_start(self):
        return self.kind == "("

    @property
    def is_block_end(self):
        return self.kind == ")"
    
    @property
    def is_word(self):
        return self.kind == "word"
    
    @property
    def is_string(self):
        return self.kind == "string"


class StfLexer:
    _EOF_TOKEN = StfToken("eof", "")
    _LEFT_PARENTHESIS_TOKEN = StfToken("(", "(")
    _RIGHT_PARENTHESIS_TOKEN = StfToken(")", ")")

    _COMMENT_KEYWORDS = frozenset({
        "skip", "SKIP", "Skip", "sKiP", "skIp", "skiP", "SKiP", "SkIp",
        "_skip", "_SKIP", "_Skip", "_sKiP", "_skIp", "_skiP", "_SKiP", "_SkIp",
        "info", "INFO", "Info", "iNfO", "inFo", "infO", "INfO", "InFo",
        "_info", "_INFO", "_Info", "_iNfO", "_inFo", "_infO", "_INfO", "_InFo",
    })
    
    def __init__(self, stream, verbose: Union[bool, int, VerbosityLevel, None] = None):
        self.stream = stream
        self.verbosity = normalize_verbosity(verbose)
        self._buffer = self.stream.read(8192)
        self._position = 0

    def next_token(self):
        while True:
            self._skip_whitespace()

            c = self._peek()

            if c == "":
                return self._EOF_TOKEN

            if c == "(":
                self._read()
                return self._LEFT_PARENTHESIS_TOKEN

            if c == ")":
                self._read()
                return self._RIGHT_PARENTHESIS_TOKEN

            if c == '"':
                return self._read_string()

            token = self._read_word()

            if token.value in self._COMMENT_KEYWORDS:
                verbose_print("stf", f"Skipping comment block keyword '{token.value}'", VerbosityLevel.DEBUG, self.verbosity)
                self._consume_comment()
                continue

            return token

    def _refill(self):
        self._buffer = self.stream.read(8192)
        self._position = 0

    def _read(self):
        if self._position >= len(self._buffer):
            self._refill()

            if not self._buffer:
                return ""

        c = self._buffer[self._position]
        self._position += 1

        return c
    
    def _peek(self):
        if self._position >= len(self._buffer):
            self._refill()

            if not self._buffer:
                return ""
            
        return self._buffer[self._position]

    def _skip_whitespace(self):
        buffer = self._buffer
        position = self._position

        while True:
            if position >= len(buffer):
                self._buffer = buffer[position:]
                self._position = 0
                self._refill()
                buffer = self._buffer
                position = self._position

                if not buffer:
                    return

            c = buffer[position]

            if c == "" or c > " ":
                self._position = position
                return

            position += 1

    def _consume_comment(self):
        self._skip_whitespace()

        buffer = self._buffer
        position = self._position
        length = len(buffer)

        if position >= length:
            self._buffer = buffer[position:]
            self._position = 0
            self._refill()
            buffer = self._buffer
            position = self._position
            length = len(buffer)

        if not buffer or buffer[position] != "(":
            raise StfReaderError("Expected '(' after comment keyword")

        position += 1 # consume opening parenthesis
        depth = 1

        while depth > 0:
            if position >= length:
                self._buffer = buffer[position:]
                self._position = 0
                self._refill()
                buffer = self._buffer
                position = self._position
                length = len(buffer)

                if not buffer:
                    raise StfReaderError("Unterminated comment")

            c = buffer[position]
            position += 1

            if c == "(":
                depth += 1

            elif c == ")":
                depth -= 1

        self._position = position

    def _read_word(self):
        buffer = self._buffer
        position = self._position
        length = len(buffer)

        parts = []
        append = parts.append

        while True:
            if position >= length:
                self._buffer = buffer[position:]
                self._position = 0
                self._refill()
                buffer = self._buffer
                position = self._position
                length = len(buffer)

                if not buffer:
                    break

            c = buffer[position]

            if c <= " " or c == "(" or c == ")":
                break

            append(c)
            position += 1
        
        self._position = position
        return StfToken("word", "".join(parts))

    def _read_string(self):
        buffer = self._buffer
        position = self._position
        length = len(buffer)

        position += 1 # consume opening quote

        parts = []
        append = parts.append

        while True:
            if position >= length:
                self._buffer = buffer[position:]
                self._position = 0
                self._refill()

                buffer = self._buffer
                position = self._position
                length = len(buffer)

                if not buffer:
                    raise StfReaderError("Unterminated string")

            c = buffer[position]

            if c == '"':
                position += 1
                break

            append(c)
            position += 1

        self._position = position

        return StfToken("string", "".join(parts))


class StfTokenStream:
    def __init__(self, lexer: StfLexer):
        self.lexer = lexer
        self.buffer = self.lexer.next_token()
        self.current = None

    def next(self) -> StfToken:
        self.current = self.buffer
        self.buffer = self.lexer.next_token()
        return self.current

    def peek(self) -> StfToken:
        return self.buffer

    def eof(self) -> bool:
        return self.buffer.is_eof


class StfReader:

    @classmethod
    def from_stream(cls, stream, filepath: str = "", verbose: Union[bool, int, VerbosityLevel, None] = None):
        lexer = StfLexer(stream, verbose=verbose)
        token_stream = StfTokenStream(lexer)

        return cls(token_stream, filepath, verbose=verbose)
    
    def __init__(self, stream: StfTokenStream, filepath: str = "", verbose: Union[bool, int, VerbosityLevel, None] = None):
        self.stream = stream
        self.filepath = filepath
        self.verbosity = normalize_verbosity(verbose)
        self.injected: Optional["StfReader"] = None
        self.id = None
        self.label = None
        self.depth = 0
        self._ended = False

    def next(self) -> StfToken:
        while self.injected is not None:
            if self.injected.eof():
                self.injected = None
                continue

            return self.injected.next()

        token = self.stream.next()

        if token.is_word and token.value == "include":
            return self._handle_include()

        return token

    def peek(self) -> StfToken:
        while self.injected is not None:
            if self.injected.eof():
                self.injected = None
                continue

            return self.injected.peek()

        return self.stream.peek()

    def inject(self, reader: "StfReader"):
        if self.injected is not None:
            reader.inject(self.injected)

        self.injected = reader

    def _expect(self, value: str):
        t = self.next()

        if t.value.lower() != value.lower():
            raise StfReaderError(f"Expected {value}, but got {t.value}")
    
    def _handle_include(self) -> StfToken:
        self._expect("(")

        include_path_token = self.next()

        if not include_path_token.is_string:
            raise StfReaderError(f"Expected string path in include, but got {include_path_token}")

        self._expect(")")

        verbose_print("stf", f"STF include detected: '{include_path_token.value}' in '{self.filepath}'", VerbosityLevel.NORMAL, self.verbosity)
        include_text = resolve_include(include_path_token.value, self.filepath, verbose=self.verbosity)
        sub_reader = StfReader.from_stream(io.StringIO(include_text), self.filepath, verbose=self.verbosity)

        self.inject(sub_reader)

        return self.next()

    def eof(self):
        return self.injected is None and self.stream.eof()

    def read_item(self):
        token = self.next()

        if token.is_eof:
            return ""

        if token.is_block_start:
            self.depth += 1
            verbose_print("stf", f"Entered block '(' (depth={self.depth})", VerbosityLevel.DEBUG, self.verbosity)

        elif token.is_block_end:
            self.depth -= 1
            verbose_print("stf", f"Exited block ')' (depth={self.depth})", VerbosityLevel.DEBUG, self.verbosity)
            if self.depth < 0:
                raise StfReaderError("Unbalanced ')' detected")

        verbose_print("stf", f"Read item: '{token.value}'", VerbosityLevel.DEBUG, self.verbosity)
        return token.value

    def read_hex(self, default=None):
        s = self.read_item()
        if s == "":
            if default is not None:
                return default
            raise StfReaderError("Unexpected EOF while reading hex")

        try:
            return int(s, 16)
        except ValueError:
            raise StfReaderError(f"Invalid hex value: {s}")

    def read_int(self, default=None):
        s = self.read_item()
        if s == "":
            if default is not None:
                return default
            raise StfReaderError("Unexpected EOF while reading int")

        try:
            return int(s, 10)
        except ValueError:
            raise StfReaderError(f"Invalid int value: {s}")

    def read_uint(self, default=None):
        value = self.read_int(default)

        if value is None:
            return None

        if value < 0:
            raise StfReaderError(f"Expected unsigned int, but got {value}")

        return value

    def read_float(self, default=None):
        s = self.read_item()
        if s == "":
            if default is not None:
                return default
            raise StfReaderError("Unexpected EOF while reading float")

        try:
            return float(s)
        except ValueError:
            raise StfReaderError(f"Invalid float value: {s}")

    def close(self):
        self._ended = True