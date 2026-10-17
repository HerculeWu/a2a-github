import json


def test_fetch_issue_text_and_json(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    out = run_cli("fetch", "issue", "2", scenario="fetch", cwd=cwd).stdout
    assert out.startswith("# #2 Crash on empty config [open]")
    data = json.loads(run_cli("fetch", "issue", "2", "--since", "2026-10-17T10:30", "--json", scenario="fetch", cwd=cwd).stdout)
    assert [c["text"] for c in data["comments"]] == ["Thanks!"]
    cut = run_cli("fetch", "issue", "2", "--max-chars", "220", scenario="fetch", cwd=cwd).stdout
    assert len(cut.rstrip("\n")) <= 220 and "[truncated" in cut


def test_fetch_pr_modes(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    for extra in ([], ["--files"], ["--diff"], ["--diff", "tests"], ["--comments-only"]):
        json.loads(run_cli("fetch", "pr", "3", *extra, "--json", scenario="fetch", cwd=cwd).stdout)
    assert "+26 -4  M  a2a/fetch.py" in run_cli("fetch", "pr", "3", "--files", scenario="fetch", cwd=cwd).stdout


def test_fetch_errors(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    assert run_cli("fetch", "issue", "404", scenario="fetch", cwd=cwd, check=False).returncode == 1
    assert run_cli("fetch", "pr", "3", "--files", "--diff", scenario="fetch", cwd=cwd, check=False).returncode == 2
    assert run_cli("fetch", "issue", "2", "--max-chars", "0", scenario="fetch", cwd=cwd, check=False).returncode == 1
