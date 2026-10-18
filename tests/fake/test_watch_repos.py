"""Watch Rounds over a Workspace that observes several repositories."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from a2a import fsio
from a2a.fake_gh import FakeGhClient
from a2a.inbox import InboxStore
from a2a.watch import run_round
from a2a.workspace import Workspace, init_workspace
from tests.conftest import load_fixture

NOON = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
LATER = NOON + timedelta(minutes=30)
BACKFILL = timedelta(hours=4)

MERGED = ["i-1002", "e-502", "e-501", "c-102", "i-1003", "c-103", "c-3001", "r-701"]


@pytest.fixture
def ws(tmp_path):
    return Workspace(init_workspace(tmp_path / ".a2a", repos=["org/repo", "org/sim"], login="me-bot", me="me-bot"))


def observe(ws, *repos):
    init_workspace(ws.root, repos=list(repos), login="me-bot", me="me-bot", force=True)


def round_(ws, gh, now=NOON, backfill=BACKFILL, warnings=None):
    cfg, _ = ws.load()
    return run_round(ws, cfg, gh, now=now, backfill=backfill, warn=(warnings if warnings is not None else []).append)


def seen(ws):
    return json.loads(ws.seen_path.read_text())


def test_entries_from_both_repos_oldest_first_each_with_repo(ws, fake_gh):
    result = round_(ws, fake_gh("watch_multi"))
    assert [e["id"] for e in result.new] == MERGED
    assert [e["repo"] for e in result.new] == ["org/repo"] * 6 + ["org/sim", "org/repo"]
    by_id = {e["id"]: e for e in result.new}
    assert by_id["c-3001"]["matched_rules"] == ["mentions"]
    assert by_id["c-3001"]["number"] == 1
    assert result.poll_interval == 90
    assert result.failed == []
    # participation is kept per repository: org/repo#1 is participated, org/sim#1 is not
    assert seen(ws)["repos"]["org/repo"]["participated"] == [1, 9]
    assert seen(ws)["repos"]["org/sim"]["participated"] == [5]


def sim_changed(routes):
    """org/sim gains one comment; org/repo is unchanged, so its probes return 304."""
    url = next(k for k in routes if k.startswith("repos/org/sim/issues/comments?"))
    first = routes[url]["body"][0]
    routes[url] = {"etag": 'W/"sim-comments-2"', "body": [
        {**first, "id": 3003, "created_at": "2026-10-17T12:40:00Z", "updated_at": "2026-10-17T12:40:00Z",
         "body": "@me-bot seed fixed", "html_url": "https://github.com/org/sim/issues/1#issuecomment-3003"},
        *routes[url]["body"],
    ]}
    return routes


def test_a_repo_whose_probes_all_return_304_writes_nothing_for_itself(ws, fake_gh):
    round_(ws, fake_gh("watch_multi"))
    before_seen = seen(ws)["repos"]["org/repo"]
    before_etags = {k: v for k, v in fsio.read_json(ws.etags_path, {}).items() if k.startswith("repos/org/repo/")}
    gh = FakeGhClient(sim_changed(load_fixture("watch_multi")))
    result = round_(ws, gh, now=LATER)
    assert [(e["id"], e["repo"]) for e in result.new] == [("c-3003", "org/sim")]
    assert seen(ws)["repos"]["org/repo"] == before_seen
    after_etags = fsio.read_json(ws.etags_path, {})
    assert {k: v for k, v in after_etags.items() if k.startswith("repos/org/repo/")} == before_etags
    assert after_etags["repos/org/sim/issues/comments?sort=updated&direction=desc&per_page=100"] == 'W/"sim-comments-2"'
    # org/repo got its four probes and nothing else
    assert len([c for c in gh.calls if "org/repo" in c["path"]]) == 4


def test_a_failing_repo_warns_and_the_other_still_saves(ws, fake_gh):
    round_(ws, fake_gh("watch_multi"))
    sim_before = seen(ws)["repos"]["org/sim"]
    etags_before = fsio.read_json(ws.etags_path, {})
    routes = load_fixture("watch_b")  # org/repo moves on; org/sim is missing, so it answers 404
    warnings = []
    result = round_(ws, FakeGhClient(routes), now=LATER, warnings=warnings)
    assert result.failed == ["org/sim"]
    assert [e["id"] for e in result.new] == ["e-504", "i-1004", "c-104", "r-702"]
    assert len(warnings) == 1 and warnings[0].startswith("org/sim skipped this round:") and "404" in warnings[0]
    assert seen(ws)["repos"]["org/sim"] == sim_before
    etags = fsio.read_json(ws.etags_path, {})
    assert {k: v for k, v in etags.items() if "org/sim" in k} == {k: v for k, v in etags_before.items() if "org/sim" in k}
    assert etags["repos/org/repo/issues/comments?sort=updated&direction=desc&per_page=100"] == 'W/"b-comments"'


def test_a_failing_first_round_leaves_no_section_and_runs_again_as_a_first_round(ws, fake_gh):
    routes = load_fixture("watch_multi")
    routes["repos/org/sim/issues/1"] = {"status": 500}
    del routes["repos/org/sim/issues?state=all&sort=updated&direction=desc&per_page=100"]["body"][0]
    result = round_(ws, FakeGhClient(routes))
    assert result.failed == ["org/sim"]
    assert list(seen(ws)["repos"]) == ["org/repo"]
    assert not any("org/sim" in k for k in fsio.read_json(ws.etags_path, {}))


def test_an_added_repo_takes_a_baseline_with_its_own_bootstrap(tmp_a2a_dir, fake_gh):
    ws = Workspace(tmp_a2a_dir)
    round_(ws, fake_gh("watch_a"))
    observe(ws, "org/repo", "org/sim")
    gh = fake_gh("watch_multi")
    assert round_(ws, gh, now=LATER, backfill=timedelta(0)).new == []
    searches = [c["path"] for c in gh.calls if c["path"].startswith("search/")]
    assert len(searches) == 3 and all("org%2Fsim" in p for p in searches)
    assert seen(ws)["repos"]["org/sim"]["initialized_at"] == "2026-10-17T12:30:00Z"
    assert seen(ws)["repos"]["org/sim"]["participated"] == [5]
    # later org/sim activity is delivered
    assert [e["id"] for e in round_(ws, FakeGhClient(sim_changed(load_fixture("watch_multi"))), now=LATER).new] == ["c-3003"]


def test_a_removed_repo_loses_its_section_and_etags(ws, fake_gh):
    round_(ws, fake_gh("watch_multi"))
    observe(ws, "org/repo")
    round_(ws, fake_gh("watch_b"), now=LATER)
    assert list(seen(ws)["repos"]) == ["org/repo"]
    assert not any("org/sim" in k for k in fsio.read_json(ws.etags_path, {}))


def test_sections_follow_the_spelling_in_repos(ws, fake_gh):
    round_(ws, fake_gh("watch_multi"))
    observe(ws, "Org/Repo", "org/sim")
    # GitHub ignores case in a repository name; the fake does not, so it gets routes in the new spelling
    routes = {k.replace("org/repo", "Org/Repo"): v for k, v in load_fixture("watch_multi").items()}
    routes = {**routes, **{k.replace("org/repo", "Org/Repo"): v for k, v in load_fixture("watch_b").items()}}
    round_(ws, FakeGhClient(routes), now=LATER)
    assert sorted(seen(ws)["repos"]) == ["Org/Repo", "org/sim"]
    assert seen(ws)["repos"]["Org/Repo"]["participated"] == [1, 9]


def flat_seen(ws):
    """Rewrite seen.json in the 0.1 shape: one repository's section at the top level."""
    data = seen(ws)["repos"]["org/repo"]
    fsio.atomic_write_json(ws.seen_path, {"version": 1, **data})


def test_a_flat_seen_is_adopted_with_one_repo(tmp_a2a_dir, fake_gh):
    ws = Workspace(tmp_a2a_dir)
    round_(ws, fake_gh("watch_a"))
    flat_seen(ws)
    gh = fake_gh("watch_b")
    result = round_(ws, gh, now=LATER, backfill=timedelta(0))
    assert [e["id"] for e in result.new] == ["e-504", "i-1004", "c-104", "r-702"]
    assert not any(c["path"].startswith("search/") for c in gh.calls)
    assert seen(ws)["repos"]["org/repo"]["participated"] == [1, 9]


def test_a_flat_seen_is_dropped_with_a_warning_with_several_repos(tmp_a2a_dir, fake_gh):
    ws = Workspace(tmp_a2a_dir)
    round_(ws, fake_gh("watch_a"))
    flat_seen(ws)
    observe(ws, "org/repo", "org/sim")
    warnings = []
    assert round_(ws, fake_gh("watch_multi"), now=LATER, backfill=timedelta(0), warnings=warnings).new == []
    assert warnings == [
        "seen.json predates repos and repos lists several repositories; starting a fresh baseline for each"
    ]
    # org/repo answered 304, so it has no section and loses its ETags: its next round is a baseline
    assert list(seen(ws)["repos"]) == ["org/sim"]
    assert not any("org/repo" in k for k in fsio.read_json(ws.etags_path, {}))


class FailingFor:
    """Raises a GhError for every call whose path names one of `repos`."""

    def __init__(self, inner, *repos):
        self.inner, self.repos = inner, repos

    def api(self, path, **kw):
        from a2a.gh import GhError

        if any(r in path for r in self.repos):
            raise GhError(f"gh api {path}: network down")
        return self.inner.api(path, **kw)


def daemon(ws, gh, rounds=2):
    from a2a.watch import run_daemon

    cfg, _ = ws.load()
    sleeps, results, warnings = [], [], []
    run_daemon(ws, cfg, gh, interval=30, on_round=results.append, backfill=BACKFILL,
               sleep=sleeps.append, warn=warnings.append, max_rounds=rounds)
    return sleeps, results, warnings


def test_daemon_sleeps_for_the_largest_poll_interval_and_does_not_back_off_for_one_failure(ws, fake_gh):
    sleeps, results, _ = daemon(ws, FailingFor(fake_gh("watch_multi"), "org/sim"))
    assert sleeps == [60]  # org/repo's X-Poll-Interval; org/sim failed
    assert results[0].failed == ["org/sim"]
    sleeps, _, _ = daemon(ws, fake_gh("watch_multi"))
    assert sleeps == [90]  # org/sim's 90 beats org/repo's 60


def test_daemon_backs_off_only_when_every_repo_failed(ws, fake_gh):
    sleeps, results, warnings = daemon(ws, FailingFor(fake_gh("watch_multi"), "org/repo", "org/sim"), rounds=3)
    assert sleeps == [30, 60]
    assert results == []
    assert "every repository failed; retrying in 30s" in warnings
