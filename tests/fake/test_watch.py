import json
from datetime import datetime, timedelta, timezone

import pytest

from a2a import fsio
from a2a.fake_gh import FakeGhClient
from a2a.inbox import InboxStore
from a2a.watch import run_round
from a2a.workspace import Workspace
from tests.conftest import FIXTURES, load_fixture

NOON = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
LATER = NOON + timedelta(minutes=30)
BACKFILL = timedelta(hours=4)

A_IDS = ["i-1002", "e-502", "e-501", "c-102", "i-1003", "c-103", "r-701"]
B_NEW = ["e-504", "i-1004", "c-104", "r-702"]


@pytest.fixture
def ws(tmp_a2a_dir):
    return Workspace(tmp_a2a_dir)


def inbox_ids(ws):
    return [e["id"] for e in InboxStore(ws.inbox_path, ws.acks_path).entries()]


def round_(ws, gh, now=NOON, backfill=BACKFILL):
    cfg, _ = ws.load()
    return run_round(ws, cfg, gh, now=now, backfill=backfill)


def test_scenario_a_produces_expected_inbox(ws, fake_gh):
    gh = fake_gh("watch_a")
    result = round_(ws, gh)
    assert [e["id"] for e in result.new] == A_IDS
    assert inbox_ids(ws) == A_IDS
    assert result.poll_interval == 60
    by_id = {e["id"]: e for e in result.new}
    assert by_id["c-102"] == {
        "id": "c-102",
        "ts": "2026-10-17T10:15:00Z",
        "type": "comment",
        "number": 2,
        "author": "alice",
        "login": "alice",
        "title": "Crash on empty config",
        "snippet": "Any update on this?",
        "url": "https://github.com/org/repo/issues/2#issuecomment-102",
        "matched_rules": ["assignee"],
    }
    assert by_id["e-501"]["snippet"] == "assignee: me-bot"
    assert by_id["e-502"]["snippet"] == "label: bug"
    assert by_id["i-1003"]["type"] == "pr_opened"
    assert by_id["i-1003"]["snippet"] == "Implements retries. cc @me-bot"
    assert by_id["c-103"]["matched_rules"] == ["participated"]
    assert by_id["r-701"]["type"] == "review"
    # the issues stream needed its second page
    assert any(c["path"].endswith("&page=2") for c in gh.calls)
    # participation was bootstrapped from search and from me-bot's own comment
    seen = json.loads(ws.seen_path.read_text())
    assert set(seen["participated"]) == {1, 9}


def test_idempotent_second_run_adds_nothing(ws, fake_gh):
    round_(ws, fake_gh("watch_a"))
    assert round_(ws, fake_gh("watch_a")).new == []
    assert inbox_ids(ws) == A_IDS


def test_idempotent_even_without_etags(ws, fake_gh):
    round_(ws, fake_gh("watch_a"))
    ws.etags_path.unlink()
    assert round_(ws, fake_gh("watch_a")).new == []
    assert inbox_ids(ws) == A_IDS


def test_all_304_round_reads_only_etags_and_writes_nothing(ws, fake_gh, monkeypatch):
    round_(ws, fake_gh("watch_a"))
    before = {p.name: p.stat().st_mtime_ns for p in ws.root.iterdir()}
    reads, writes = [], []
    real_read_json, real_read_jsonl = fsio.read_json, fsio.read_jsonl
    monkeypatch.setattr(fsio, "read_json", lambda p, d: reads.append(p.name) or real_read_json(p, d))
    monkeypatch.setattr(fsio, "read_jsonl", lambda p: reads.append(p.name) or real_read_jsonl(p))
    for name in ("atomic_write_json", "atomic_write_text", "append_jsonl"):
        monkeypatch.setattr(fsio, name, lambda p, *a, _n=name: writes.append((_n, p.name)))
    gh = fake_gh("watch_a")
    result = round_(ws, gh, now=LATER)
    assert result.new == []
    assert reads == ["etags.json"]
    assert writes == []
    assert {p.name: p.stat().st_mtime_ns for p in ws.root.iterdir()} == before
    assert [c["etag"] for c in gh.calls] == ['W/"a-issues"', 'W/"a-comments"', 'W/"a-rc"', 'W/"a-events"']


def test_incremental_superset_adds_only_the_difference(ws, fake_gh):
    round_(ws, fake_gh("watch_a"))
    result = round_(ws, fake_gh("watch_b"), now=LATER)
    assert [e["id"] for e in result.new] == B_NEW
    assert inbox_ids(ws) == A_IDS + B_NEW
    by_id = {e["id"]: e for e in result.new}
    assert by_id["i-1004"]["matched_rules"] == ["labels:pin:me-bot"]
    assert by_id["c-104"]["matched_rules"] == ["participated"]
    assert by_id["c-104"]["title"] == "Old discussion"
    assert by_id["r-702"]["snippet"] == "fetch.py: nit: rename, @me-bot thoughts?"
    assert by_id["r-702"]["matched_rules"] == ["mentions"]
    assert result.poll_interval == 120


def test_first_run_without_backfill_ignores_history(ws, fake_gh):
    assert round_(ws, fake_gh("watch_a"), backfill=timedelta(0)).new == []
    assert round_(ws, fake_gh("watch_b"), now=LATER, backfill=timedelta(0)).new == []


def test_first_run_without_backfill_delivers_nothing_even_minutes_old(ws, fake_gh):
    # The latest fixture Activity is at 10:30, inside the overlap window below a 10:35 cursor.
    just_after = datetime(2026, 10, 17, 10, 35, tzinfo=timezone.utc)
    assert round_(ws, fake_gh("watch_a"), now=just_after, backfill=timedelta(0)).new == []
    assert "c-103" in fsio.read_json(ws.seen_path, {})["recent"]


def test_first_run_backfill_delivers_only_from_its_start(ws, fake_gh):
    just_after = datetime(2026, 10, 17, 10, 35, tzinfo=timezone.utc)
    new = round_(ws, fake_gh("watch_a"), now=just_after, backfill=timedelta(minutes=10)).new
    assert new and all(e["ts"] >= "2026-10-17T10:25:00Z" for e in new)


def test_thread_snapshot_fetched_when_not_in_issue_stream(ws, fake_gh):
    round_(ws, fake_gh("watch_a"))
    routes = load_fixture("watch_b")
    issues_url = next(k for k in routes if "/issues?state=all" in k)
    routes[issues_url]["body"] = [i for i in routes[issues_url]["body"] if i["number"] != 9]
    gh = FakeGhClient(routes)
    result = round_(ws, gh, now=LATER)
    assert "c-104" in [e["id"] for e in result.new]
    assert any(c["path"] == "repos/org/repo/issues/9" for c in gh.calls)


def test_shared_login_agent_sees_human_but_not_itself(tmp_path, fake_gh):
    from a2a.workspace import init_workspace

    root = init_workspace(tmp_path / "agent-x", repo="org/repo", login="me-bot", me="agent-x")
    ws = Workspace(root)
    routes = load_fixture("watch_a")
    comments_url = next(k for k in routes if "/issues/comments?" in k)
    base = routes[comments_url]["body"][0]
    routes[comments_url]["body"] = [
        {**base, "id": 901, "user": {"login": "me-bot"}, "created_at": "2026-10-17T11:00:00Z",
         "updated_at": "2026-10-17T11:00:00Z", "body": "@agent-x mine\n<!-- a2a:from=agent-x -->"},
        {**base, "id": 902, "user": {"login": "me-bot"}, "created_at": "2026-10-17T11:01:00Z",
         "updated_at": "2026-10-17T11:01:00Z", "body": "@agent-x from the human"},
    ]
    gh = FakeGhClient(routes)
    result = round_(ws, gh)
    ids = [e["id"] for e in result.new]
    assert "c-902" in ids and "c-901" not in ids
    # shared login: no search bootstrap
    assert not any(c["path"].startswith("search/") for c in gh.calls)
    # agent-x participated in #1 through its signed comment
    assert 1 in json.loads(ws.seen_path.read_text())["participated"]


def test_daemon_sleeps_by_poll_interval_and_backs_off_on_errors(ws, fake_gh):
    from a2a.gh import GhError
    from a2a.watch import run_daemon

    class Flaky:
        def __init__(self, inner):
            self.inner, self.n = inner, 0

        def api(self, path, **kw):
            self.n += 1
            if self.n == 1:
                raise GhError("network down")
            return self.inner.api(path, **kw)

    cfg, _ = ws.load()
    sleeps, rounds, warnings = [], [], []
    run_daemon(ws, cfg, Flaky(fake_gh("watch_a")), interval=30, on_round=rounds.append, backfill=BACKFILL,
               sleep=sleeps.append, warn=warnings.append, max_rounds=3)
    assert sleeps == [30, 60]  # backoff after the error, then X-Poll-Interval 60 > interval 30
    assert len(rounds) == 2
    assert "network down" in warnings[0]


def test_watch_lock_is_exclusive(ws):
    from a2a.watch import watch_lock

    with watch_lock(ws):
        with pytest.raises(BlockingIOError):
            with watch_lock(ws):
                pass


def test_seen_stays_bounded_even_when_a_stream_is_quiet():
    from a2a.watch import Seen

    seen = Seen.first_run(NOON - timedelta(days=30), NOON - timedelta(days=30))
    seen.cursors.update(issues=NOON, comments=NOON, events=NOON, reviews=NOON)  # review_comments stays quiet
    seen.recent = {"c-1": "2026-10-16T12:00:00Z", "c-2": "2026-10-17T11:55:00Z", "e-3": "2026-10-01T00:00:00Z"}
    assert seen.to_json()["recent"] == {"c-2": "2026-10-17T11:55:00Z"}
