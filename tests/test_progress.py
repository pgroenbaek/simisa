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

import pytest

from simisa.progress import ProgressReporter


def test_no_callback_does_nothing():
    reporter = ProgressReporter()

    reporter.report("Reading", 50, 100)
    reporter.complete()


def test_first_report_triggers_callback():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.report("Reading", 25, 100)

    assert calls == [
        ("Reading", 0.25),
    ]


def test_progress_is_calculated_from_bytes():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.report("Reading", 75, 100)

    assert calls == [
        ("Reading", 0.75),
    ]


def test_progress_is_clamped_to_zero():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.report("Reading", -10, 100)

    assert calls == [
        ("Reading", 0.0),
    ]


def test_progress_is_clamped_to_one():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.report("Reading", 150, 100)

    assert calls == [
        ("Reading", 1.0),
    ]


def test_zero_total_bytes_reports_zero():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.report("Reading", 0, 0)

    assert calls == [
        ("Reading", 0.0),
    ]


def test_negative_total_bytes_reports_zero():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.report("Reading", 10, -1)

    assert calls == [
        ("Reading", 0.0),
    ]


def test_same_message_is_throttled():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress)),
        interval=0.1,
    )

    reporter.report("Reading", 10, 100)
    reporter.report("Reading", 15, 100)
    reporter.report("Reading", 19, 100)

    assert calls == [
        ("Reading", 0.1),
    ]


def test_same_message_reports_after_interval():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress)),
        interval=0.1,
    )

    reporter.report("Reading", 10, 100)
    reporter.report("Reading", 15, 100)
    reporter.report("Reading", 20, 100)

    assert calls == [
        ("Reading", 0.1),
        ("Reading", 0.2),
    ]


def test_message_change_bypasses_throttling():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress)),
        interval=0.1,
    )

    reporter.report("Reading vertices", 10, 100)
    reporter.report("Reading normals", 11, 100)

    assert calls == [
        ("Reading vertices", 0.1),
        ("Reading normals", 0.11),
    ]


def test_completion_progress_always_reports():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress)),
        interval=0.5,
    )

    reporter.report("Reading", 90, 100)
    reporter.report("Reading", 100, 100)

    assert calls == [
        ("Reading", 0.9),
        ("Reading", 1.0),
    ]


def test_complete_reports_one():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.report("Reading", 50, 100)
    reporter.complete()

    assert calls == [
        ("Reading", 0.5),
        ("Finished", 1.0),
    ]


def test_complete_accepts_custom_message():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.complete("Finished writing")

    assert calls == [
        ("Finished writing", 1.0),
    ]


def test_duplicate_complete_is_not_reported():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.complete()
    reporter.complete()

    assert calls == [
        ("Finished", 1.0),
    ]


def test_complete_with_different_message_is_reported():
    calls = []

    reporter = ProgressReporter(
        lambda message, progress: calls.append((message, progress))
    )

    reporter.complete("Finished reading")
    reporter.complete("Finished")

    assert calls == [
        ("Finished reading", 1.0),
        ("Finished", 1.0),
    ]


def test_callback_exception_propagates():
    def callback(message, progress):
        raise RuntimeError("callback failed")

    reporter = ProgressReporter(callback)

    with pytest.raises(RuntimeError, match="callback failed"):
        reporter.report("Reading", 50, 100)


@pytest.mark.parametrize(
    "callback",
    [
        123,
        "callback",
        [],
        {},
        object(),
    ],
)
def test_rejects_non_callable_callback(callback):
    with pytest.raises(TypeError):
        ProgressReporter(callback)


@pytest.mark.parametrize(
    "interval",
    [
        "0.1",
        [],
        {},
        object(),
    ],
)
def test_rejects_invalid_interval_type(interval):
    with pytest.raises(TypeError):
        ProgressReporter(interval=interval)


@pytest.mark.parametrize(
    "interval",
    [
        -0.1,
        1.1,
        2,
        -1,
    ],
)
def test_rejects_interval_outside_range(interval):
    with pytest.raises(ValueError):
        ProgressReporter(interval=interval)


@pytest.mark.parametrize(
    "interval",
    [
        0.0,
        0.01,
        0.5,
        1.0,
    ],
)
def test_accepts_valid_interval(interval):
    ProgressReporter(interval=interval)


@pytest.mark.parametrize(
    "message",
    [
        123,
        None,
        [],
        {},
    ],
)
def test_report_rejects_non_string_message(message):
    reporter = ProgressReporter(lambda message, progress: None)

    with pytest.raises(TypeError):
        reporter.report(message, 0, 100)


@pytest.mark.parametrize(
    "message",
    [
        123,
        None,
        [],
        {},
    ],
)
def test_complete_rejects_non_string_message(message):
    reporter = ProgressReporter(lambda message, progress: None)

    with pytest.raises(TypeError):
        reporter.complete(message)

def test_accepts_callback_with_two_positional_arguments():
    def callback(message, progress):
        pass

    ProgressReporter(callback)


def test_accepts_bound_method_callback():
    class Handler:
        def callback(self, message, progress):
            pass

    ProgressReporter(Handler().callback)


def test_accepts_callback_with_additional_optional_arguments():
    def callback(message, progress, extra=None):
        pass

    ProgressReporter(callback)


def test_accepts_callback_with_varargs():
    def callback(*args):
        pass

    ProgressReporter(callback)


def test_rejects_callback_with_no_arguments():
    def callback():
        pass

    with pytest.raises(TypeError, match="must accept two positional arguments"):
        ProgressReporter(callback)


def test_rejects_callback_with_one_argument():
    def callback(message):
        pass

    with pytest.raises(TypeError, match="must accept two positional arguments"):
        ProgressReporter(callback)


def test_rejects_callback_with_required_third_argument():
    def callback(message, progress, extra):
        pass

    with pytest.raises(TypeError, match="must accept two positional arguments"):
        ProgressReporter(callback)


def test_rejects_keyword_only_callback():
    def callback(*, message, progress):
        pass

    with pytest.raises(TypeError, match="must accept two positional arguments"):
        ProgressReporter(callback)


def test_rejects_non_callable_callback():
    with pytest.raises(TypeError, match="must be callable or None"):
        ProgressReporter("not callable")