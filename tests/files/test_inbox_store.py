import json

import pytest

from a2a.inbox import InboxError, InboxStore


def make_entries():
    return [
        {"id": "i-1", "ts": "2026-10-17T10:00:00Z", "type": "issue_opened", "number": 5, "author": "alice", "snippet": "a"},
        {"id": "c-2", "ts": "2026-10-17T11:00:00Z", "type": "comment", "number": 5, "author": "bob", "snippet": "b"},
        {"id": "e-3", "ts": "2026-10-17T12:00:00Z", "type": "assigned", "number": 9, "author": "carol", "snippet": "c"},
        {"id": "r-4", "ts": "2026-10-17T13:00:00Z", "type": "review", "number": 9, "author": "dan", "snippet": "d"},
    ]


@pytest.fixture
def store(tmp_a2a_dir):
    s = InboxStore(tmp_a2a_dir / "inbox.jsonl", tmp_a2a_dir / "acks.json")
    assert s.append(make_entries()) == 4
    return s


def test_append_skips_ids_already_present(store):
    assert store.append(make_entries()[:2] + [{**make_entries()[0], "id": "i-new"}]) == 1
    assert [e["id"] for e in store.list()] == ["i-1", "c-2", "e-3", "r-4", "i-new"]


def test_list_filters(store):
    assert [e["id"] for e in store.list(types=["comment", "review"])] == ["c-2", "r-4"]
    assert [e["id"] for e in store.list(since="2026-10-17T11:30")] == ["e-3", "r-4"]
    assert [e["id"] for e in store.list(limit=2)] == ["e-3", "r-4"]
    assert all(e["read"] is False for e in store.list())


def test_ack_by_id_number_and_all(store, tmp_a2a_dir):
    assert store.ack(["c-2"]) == ["c-2"]
    assert [e["id"] for e in store.list(unread=True)] == ["i-1", "e-3", "r-4"]
    assert store.ack(["#9"]) == ["e-3", "r-4"]
    assert [e["id"] for e in store.list(unread=True)] == ["i-1"]
    assert store.count(unread=True) == 1
    assert store.ack(all_=True) == ["i-1"]
    assert store.count(unread=True) == 0
    assert store.count() == 4
    # files stay valid
    for line in (tmp_a2a_dir / "inbox.jsonl").read_text().splitlines():
        assert "read" not in json.loads(line)
    assert json.loads((tmp_a2a_dir / "acks.json").read_text())["ids"] == ["c-2", "e-3", "i-1", "r-4"]


def test_ack_twice_reports_nothing_new(store):
    store.ack(["c-2"])
    assert store.ack(["c-2"]) == []


def test_ack_unknown_id_errors(store):
    with pytest.raises(InboxError):
        store.ack(["c-999"])


def test_ack_thread_without_entries_acks_nothing(store):
    assert store.ack(["#404"]) == []


def test_ack_failure_before_replace_keeps_acks(store, tmp_a2a_dir, monkeypatch):
    import os

    store.ack(["c-2"])

    def boom(*a, **k):
        raise RuntimeError("killed")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RuntimeError):
        store.ack(all_=True)
    monkeypatch.undo()
    assert json.loads((tmp_a2a_dir / "acks.json").read_text())["ids"] == ["c-2"]
    assert store.count(unread=True) == 3
