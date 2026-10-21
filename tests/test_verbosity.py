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

import logging

import pytest

from simisa.verbosity import normalize_verbosity, verbosity_enabled


@pytest.mark.parametrize(
    "verbose, expected",
    [
        (None, None),
        (False, None),
        (True, logging.INFO),
        (logging.INFO, logging.INFO),
        (logging.DEBUG, logging.DEBUG),
    ],
)
def test_normalize_verbosity_valid_values(verbose, expected):
    assert normalize_verbosity(verbose) == expected


@pytest.mark.parametrize(
    "verbose",
    [
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
        0,
        1,
        15,
        100,
        -1,
    ],
)
def test_normalize_verbosity_rejects_unsupported_logging_levels(verbose):
    with pytest.raises(ValueError):
        normalize_verbosity(verbose)


@pytest.mark.parametrize(
    "verbose",
    [
        "DEBUG",
        "INFO",
        1.0,
        [],
        {},
        object(),
    ],
)
def test_normalize_verbosity_rejects_invalid_types(verbose):
    with pytest.raises(TypeError):
        normalize_verbosity(verbose)


def test_verbosity_enabled_none_disables_all_levels():
    assert verbosity_enabled(None, logging.INFO) is False
    assert verbosity_enabled(None, logging.DEBUG) is False


def test_verbosity_enabled_info_enables_info():
    assert verbosity_enabled(logging.INFO, logging.INFO) is True


def test_verbosity_enabled_info_does_not_enable_debug():
    assert verbosity_enabled(logging.INFO, logging.DEBUG) is False


def test_verbosity_enabled_debug_enables_debug():
    assert verbosity_enabled(logging.DEBUG, logging.DEBUG) is True


def test_verbosity_enabled_debug_enables_info():
    assert verbosity_enabled(logging.DEBUG, logging.INFO) is True


def test_verbosity_enabled_defaults_to_info():
    assert verbosity_enabled(logging.INFO) is True
    assert verbosity_enabled(logging.DEBUG) is True
    assert verbosity_enabled(None) is False
