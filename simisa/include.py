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

import os
import re
import codecs
from typing import Optional, Union

from .verbose import VerbosityLevel, normalize_verbosity, verbose_print



class UnresolvableIncludeError(Exception):
    """Raised when an include block cannot be resolved."""
    pass


def has_includes(text: str) -> bool:
    """
    Determines whether text contains any include statements.

    Args:
        text: Text to inspect.

    Returns:
        True if the text contains include statements,
        otherwise False.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"Parameter 'text' must be str, but got {type(text).__name__}"
        )

    include_re = re.compile(
        r'include\s*\(\s*([\'"])(.*?)\1\s*\)',
        re.IGNORECASE | re.DOTALL
    )

    return include_re.search(text) is not None


def peek_first_include(filepath: str) -> Optional[str]:
    """
    Reads the beginning of a file and extracts the first include path if present.

    The function decodes a small prefix of the file (UTF-16 LE if BOM is present,
    otherwise ASCII), skips leading comment blocks, and checks whether the
    first real construct is an include statement.

    If any other construct appears before include, the file is binary,
    or no valid include is found, None is returned.

    Args:
        filepath: Path to the file to inspect.

    Returns:
        The first include path if present, otherwise None.
    """
    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )

    with open(filepath, "rb") as f:
        bom = f.read(2)
        is_unicode = (bom == codecs.BOM_UTF16_LE)
        encoding = "utf-16-le" if is_unicode else "ascii"

        # Assumption: First include is within the first 2kB of the file
        # This might not be true if there is a very long comment beforehand.
        data = f.read(2048)

        buffer = bom + data

        try:
            text = buffer.decode(encoding)
        except UnicodeDecodeError:
            return None

    text = text.lstrip("\ufeff")

    comment_block_re = re.compile(
        r'^(?:\s*(skip|_skip|comment|_comment|info|_info)\s*\(.*?\)\s*)+',
        re.IGNORECASE | re.DOTALL
    )

    include_re = re.compile(
        r'^\s*include\s*\(\s*([\'"])(.*?)\1\s*\)\s*',
        re.IGNORECASE | re.DOTALL
    )

    first_token_re = re.compile(
        r'^\s*([A-Za-z_][A-Za-z0-9_]*)',
        re.DOTALL
    )

    text = comment_block_re.sub("", text).lstrip()

    first_token_match = first_token_re.match(text)

    if not first_token_match:
        return None

    first_token = first_token_match.group(1).lower()

    if first_token != "include":
        return None

    include_match = include_re.match(text)

    if not include_match:
        return None

    return include_match.group(2)


def resolve_include(include_path: str, filepath: str, verbose: Union[bool, int, VerbosityLevel, None] = None) -> str:
    """
    Resolves a single include (by path relative to `filepath`)
    and returns its fully expanded content (including nested includes).

    Args:
        include_path: Path of the include to resolve (relative to `filepath`).
        filepath: Base file path used to resolve the include path.
        verbose: Optional verbosity level.

    Returns:
        Fully expanded content of the included file.

    Raises:
        UnresolvableIncludeError: If the include cannot be found or decoded.
    """
    if not isinstance(include_path, str):
        raise TypeError(
            f"Parameter 'include_path' must be str, but got {type(include_path).__name__}"
        )

    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )

    vlevel = normalize_verbosity(verbose)
    verbose_print("include", f"Resolving include '{include_path}' relative to '{filepath}'", VerbosityLevel.NORMAL, vlevel)

    base_dir = os.path.dirname(filepath)

    include_filepath = os.path.normpath(
        os.path.join(base_dir, include_path)
    )

    if not os.path.isfile(include_filepath):
        verbose_print("include", f"Failed to resolve include: file '{include_filepath}' not found", VerbosityLevel.DEBUG, vlevel)
        raise UnresolvableIncludeError(
            f"Could not resolve include '{include_path}' from '{filepath}'"
        )

    with open(include_filepath, "rb") as f:
        bom = f.read(2)
        is_unicode = (bom == codecs.BOM_UTF16_LE)
        encoding = "utf-16-le" if is_unicode else "ascii"

        data = f.read()
        buffer = bom + data

        try:
            include_text = buffer.decode(encoding)
        except UnicodeDecodeError as e:
            raise UnresolvableIncludeError(
                f"Could not decode include '{include_filepath}'"
            ) from e

    verbose_print("include", f"Successfully loaded include '{include_filepath}'", VerbosityLevel.NORMAL, vlevel)
    return resolve_includes(include_text, include_filepath, verbose=verbose)


def resolve_includes(text: str, filepath: str, verbose: Union[bool, int, VerbosityLevel, None] = None) -> str:
    """
    Resolves all include statements recursively and returns the fully
    expanded text.

    Included file paths are resolved relative to the file currently
    being processed.

    Args:
        text: Source text to resolve includes in.
        filepath: Path of the source file the text originated from.
        verbose: Optional verbosity level.

    Returns:
        The full text with all includes resolved.

    Raises:
        UnresolvableIncludeError:
            If an included file cannot be found or decoded.
    """
    if not isinstance(text, str):
        raise TypeError(
            f"Parameter 'text' must be str, but got {type(text).__name__}"
        )

    if not isinstance(filepath, str):
        raise TypeError(
            f"Parameter 'filepath' must be str, but got {type(filepath).__name__}"
        )

    vlevel = normalize_verbosity(verbose)
    include_re = re.compile(
        r'include\s*\(\s*([\'"])(.*?)\1\s*\)',
        re.IGNORECASE
    )

    base_dir = os.path.dirname(filepath)

    while True:
        include_match = include_re.search(text)

        if not include_match:
            break

        include_path = include_match.group(2)
        verbose_print("include", f"Found include statement: '{include_path}' in '{filepath}'", VerbosityLevel.NORMAL, vlevel)

        include_filepath = os.path.normpath(
            os.path.join(base_dir, include_path)
        )

        if not os.path.isfile(include_filepath):
            verbose_print("include", f"Failed to resolve include: file '{include_filepath}' not found", VerbosityLevel.DEBUG, vlevel)
            raise UnresolvableIncludeError(
                f"Could not resolve include '{include_path}' "
                f"from '{filepath}'"
            )

        with open(include_filepath, "rb") as f:
            bom = f.read(2)
            is_unicode = (bom == codecs.BOM_UTF16_LE)
            encoding = "utf-16-le" if is_unicode else "ascii"

            data = f.read()

            buffer = bom + data

            try:
                include_text = buffer.decode(encoding)
            except UnicodeDecodeError as e:
                raise UnresolvableIncludeError(
                    f"Could not decode include '{include_filepath}'"
                ) from e

        verbose_print("include", f"Loaded include '{include_filepath}', expanding recursively", VerbosityLevel.NORMAL, vlevel)
        include_text = resolve_includes(
            include_text,
            include_filepath,
            verbose=verbose
        )

        text = (
            text[:include_match.start()] +
            include_text +
            text[include_match.end():]
        )

    return text