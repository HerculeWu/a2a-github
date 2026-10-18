from a2a.fetch import fetch_issue, fetch_pr
from a2a.timeutil import parse_iso

REPO = "org/repo"


def test_fetch_issue_full(fake_gh):
    out = fetch_issue(fake_gh("fetch"), REPO, 2)
    assert out.text == (
        "# org/repo#2 Crash on empty config [open]\n"
        "alice · 2026-10-17T10:10Z · labels: bug · assignees: me-bot · https://github.com/org/repo/issues/2\n\n"
        "Steps to reproduce:\n1. empty config\n2. boom\n\n"
        "## Comments (3)\n"
        "### alice · 2026-10-17T10:15Z\nAny update on this?\n\n"
        "### agent-x · 2026-10-17T10:20Z\nOn it.\n\n"
        "### alice · 2026-10-17T11:00Z\nThanks!"
    )
    assert out.data["comments"][1] == {"author": "agent-x", "login": "me-bot", "ts": "2026-10-17T10:20:00Z", "text": "On it."}
    assert out.data["truncated"] is False


def test_fetch_issue_since_and_comments_only(fake_gh):
    out = fetch_issue(fake_gh("fetch"), REPO, 2, since=parse_iso("2026-10-17T10:15"), comments_only=True)
    assert "Steps to reproduce" not in out.text
    assert "## Comments (2 of 3 after 2026-10-17T10:15Z)" in out.text
    assert "Any update" not in out.text
    assert out.data["body"] is None


def test_fetch_issue_on_a_pr_says_so(fake_gh):
    assert fetch_issue(fake_gh("fetch"), REPO, 3).text.startswith("# org/repo#3 Add retry to fetcher [open · PR]")


def test_fetch_pr_timeline(fake_gh):
    out = fetch_pr(fake_gh("fetch"), REPO, 3)
    lines = out.text.splitlines()
    assert lines[0] == "# org/repo#3 Add retry to fetcher [open · PR]"
    assert lines[1] == "bob · 2026-10-17T10:20Z · main ← retry · +30 -4 in 2 files · https://github.com/org/repo/pull/3"
    assert "## Timeline (3)" in out.text
    assert "### dan · review APPROVED · 2026-10-17T10:50Z\nLGTM @me-bot" in out.text
    assert "### dan · review COMMENTED · 2026-10-17T11:40Z\n- fetch.py:10: nit: rename" in out.text
    assert "draft" not in out.text  # pending review skipped
    assert out.text.index("Nice.") < out.text.index("LGTM")


def test_fetch_pr_files(fake_gh):
    out = fetch_pr(fake_gh("fetch"), REPO, 3, files=True)
    assert out.text.splitlines()[-2:] == ["+26 -4  M  a2a/fetch.py", "+4 -0  A  tests/test_retry.py"]
    assert out.data["files"][1] == {"path": "tests/test_retry.py", "status": "added", "additions": 4, "deletions": 0}


def test_fetch_pr_diff_full_and_by_path(fake_gh):
    full = fetch_pr(fake_gh("fetch"), REPO, 3, diff=True)
    assert "```diff\ndiff --git a/a2a/fetch.py" in full.text and "tests/test_retry.py" in full.text
    only = fetch_pr(fake_gh("fetch"), REPO, 3, diff=True, paths=["tests"])
    assert "a2a/fetch.py" not in only.text.split("```diff")[1]
    assert "+def test(): pass" in only.text
    cut = fetch_pr(fake_gh("fetch"), REPO, 3, diff=True, max_chars=200)
    assert len(cut.text) <= 200 and cut.text.endswith("[truncated]") and cut.data["truncated"]


def test_the_header_names_the_thread_with_its_repo(fake_gh):
    out = fetch_issue(fake_gh("fetch"), "lab/sim", 7)
    assert out.text.splitlines()[0] == "# lab/sim#7 Sim run diverges [open]"
    assert (out.data["repo"], out.data["number"]) == ("lab/sim", 7)


def test_every_pr_view_carries_repo_and_number(fake_gh):
    for kw in ({}, {"files": True}, {"diff": True}):
        data = fetch_pr(fake_gh("fetch"), REPO, 3, **kw).data
        assert (data["repo"], data["number"]) == (REPO, 3)
