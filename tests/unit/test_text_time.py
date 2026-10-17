from datetime import datetime, timezone

import pytest

from a2a.text import display_width, snippet, truncate_display
from a2a.timeutil import fmt_iso, fmt_short, parse_duration, parse_iso


def test_snippet_collapses_lines():
    assert snippet("line one\n\n  line two\r\n\tthree") == "line one line two three"


def test_snippet_cuts_long_text_to_200_code_points_with_ellipsis():
    s = snippet("x" * 500)
    assert len(s) == 200
    assert s.endswith("…")


def test_snippet_keeps_exactly_200():
    assert snippet("y" * 200) == "y" * 200


def test_snippet_emoji_counts_code_points():
    s = snippet("😀" * 300)
    assert len(s) == 200
    assert s[:199] == "😀" * 199


def test_snippet_empty_and_none():
    assert snippet("") == ""
    assert snippet(None) == ""
    assert snippet("   \n ") == ""


def test_display_width_counts_wide_chars_double():
    assert display_width("abc") == 3
    assert display_width("能不能") == 6


def test_truncate_display():
    assert truncate_display("abc", 10) == "abc"
    assert truncate_display("abcdefghij", 5) == "abcd…"
    assert truncate_display("能不能改成这样吗", 9) == "能不能改…"


def test_parse_iso_variants():
    want = datetime(2026, 10, 17, 17, 40, tzinfo=timezone.utc)
    assert parse_iso("2026-10-17T17:40:00Z") == want
    assert parse_iso("2026-10-17T17:40") == want
    assert parse_iso("2026-10-17T19:40:00+02:00") == want
    assert parse_iso("2026-10-17") == datetime(2026, 10, 17, tzinfo=timezone.utc)


def test_parse_iso_rejects_garbage():
    with pytest.raises(ValueError):
        parse_iso("yesterday")


def test_formatting():
    dt = datetime(2026, 10, 17, 17, 40, 5, tzinfo=timezone.utc)
    assert fmt_iso(dt) == "2026-10-17T17:40:05Z"
    assert fmt_short(dt) == "2026-10-17T17:40"


@pytest.mark.parametrize("text,seconds", [("0", 0), ("90s", 90), ("15m", 900), ("2h", 7200), ("7d", 604800), ("1w", 604800)])
def test_parse_duration(text, seconds):
    assert parse_duration(text).total_seconds() == seconds


def test_parse_duration_rejects_garbage():
    with pytest.raises(ValueError):
        parse_duration("soon")
