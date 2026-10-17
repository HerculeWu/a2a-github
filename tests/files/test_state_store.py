import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from a2a.state import StateStore

ROOT = Path(__file__).resolve().parents[2]


def test_round_trip_nested_and_unicode(tmp_path):
    s = StateStore(tmp_path / "state.json")
    s.set("cursor", {"issues": [1, 2, {"deep": "值 😀"}]})
    s.set("名前", "エージェント")
    assert s.get("cursor") == {"issues": [1, 2, {"deep": "值 😀"}]}
    assert s.get("名前") == "エージェント"
    assert StateStore(tmp_path / "state.json").dump() == {"cursor": {"issues": [1, 2, {"deep": "值 😀"}]}, "名前": "エージェント"}


def test_get_missing_raises_keyerror(tmp_path):
    with pytest.raises(KeyError):
        StateStore(tmp_path / "state.json").get("nope")


def test_delete_is_idempotent(tmp_path):
    s = StateStore(tmp_path / "state.json")
    s.set("k", 1)
    assert s.delete("k") is True
    assert s.delete("k") is False
    assert s.dump() == {}


def test_failure_before_replace_keeps_old_state(tmp_path, monkeypatch):
    s = StateStore(tmp_path / "state.json")
    s.set("k", "old")

    def boom(*a, **k):
        raise RuntimeError("killed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RuntimeError):
        s.set("k", "new")
    monkeypatch.undo()
    assert json.loads((tmp_path / "state.json").read_text()) == {"k": "old"}


def test_corrupt_state_is_reported(tmp_path):
    (tmp_path / "state.json").write_text("[1, 2]")
    with pytest.raises(ValueError):
        StateStore(tmp_path / "state.json").dump()


WRITER = """
import sys
from a2a.state import StateStore
store = StateStore(sys.argv[1])
for i in range(int(sys.argv[3])):
    store.set(f"{sys.argv[2]}-{i}", i)
"""


def test_concurrent_processes_setting_different_keys_all_survive(tmp_path):
    path = tmp_path / "state.json"
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    procs = [
        subprocess.Popen([sys.executable, "-c", WRITER, str(path), name, "40"], env=env) for name in ("a", "b")
    ]
    assert [p.wait(timeout=60) for p in procs] == [0, 0]
    data = StateStore(path).dump()
    assert {f"a-{i}" for i in range(40)} | {f"b-{i}" for i in range(40)} == set(data)
