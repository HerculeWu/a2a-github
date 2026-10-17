import json
import os

import pytest

from a2a import fsio


def test_atomic_write_json_round_trip(tmp_path):
    p = tmp_path / "x.json"
    fsio.atomic_write_json(p, {"k": "值", "n": [1, {"a": None}]})
    assert fsio.read_json(p, {}) == {"k": "值", "n": [1, {"a": None}]}


def test_read_json_default_when_missing(tmp_path):
    assert fsio.read_json(tmp_path / "missing.json", {"d": 1}) == {"d": 1}


def test_failure_before_replace_keeps_original_and_cleans_tmp(tmp_path, monkeypatch):
    p = tmp_path / "x.json"
    fsio.atomic_write_json(p, {"v": 1})

    def boom(*a, **k):
        raise KeyboardInterrupt("killed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(KeyboardInterrupt):
        fsio.atomic_write_json(p, {"v": 2})
    assert json.loads(p.read_text()) == {"v": 1}
    assert sorted(f.name for f in tmp_path.iterdir()) == ["x.json"]


def test_append_lines_appends_jsonl(tmp_path):
    p = tmp_path / "log.jsonl"
    fsio.append_jsonl(p, [{"a": 1}])
    fsio.append_jsonl(p, [{"b": "二"}, {"c": 3}])
    assert fsio.read_jsonl(p) == [{"a": 1}, {"b": "二"}, {"c": 3}]


def test_read_jsonl_skips_torn_last_line(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"a": 1}\n{"b": ', encoding="utf-8")
    assert fsio.read_jsonl(p) == [{"a": 1}]


def test_lock_is_exclusive(tmp_path):
    p = tmp_path / "x.json"
    with fsio.locked(p):
        with pytest.raises(BlockingIOError):
            with fsio.locked(p, blocking=False):
                pass
