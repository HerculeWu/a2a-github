import pytest

from a2a.state import format_value, parse_value


@pytest.mark.parametrize(
    "text,value",
    [
        ("42", 42),
        ("true", True),
        ("null", None),
        ('{"a": [1, "二"]}', {"a": [1, "二"]}),
        ('"quoted"', "quoted"),
        ("reviewing", "reviewing"),
        ("not json {", "not json {"),
    ],
)
def test_parse_value_json_then_string(text, value):
    assert parse_value(text) == value


def test_parse_value_raw_keeps_string():
    assert parse_value("true", raw=True) == "true"
    assert parse_value("42", raw=True) == "42"


def test_format_value():
    assert format_value("plain") == "plain"
    assert format_value({"a": 1}) == '{"a":1}'
    assert format_value("值") == "值"
    assert format_value(None) == "null"
