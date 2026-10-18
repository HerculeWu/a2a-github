import json


def test_fetch_issue_text_and_json(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    out = run_cli("fetch", "issue", "2", scenario="fetch", cwd=cwd).stdout
    assert out.startswith("# org/repo#2 Crash on empty config [open]")
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


def test_fetch_takes_a_thread_name(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    data = json.loads(run_cli("fetch", "issue", "ORG/REPO#2", "--json", scenario="fetch", cwd=cwd).stdout)
    assert (data["repo"], data["number"]) == ("org/repo", 2)
    assert run_cli("fetch", "issue", "#2", scenario="fetch", cwd=cwd).stdout.startswith("# org/repo#2 ")
    assert run_cli("fetch", "pr", "org/repo#3", "--files", scenario="fetch", cwd=cwd).stdout.startswith("# org/repo#3 ")


def test_fetch_reaches_a_repo_outside_repos(run_cli, tmp_a2a_dir):
    out = run_cli("fetch", "issue", "lab/sim#7", scenario="fetch", cwd=tmp_a2a_dir.parent).stdout
    assert out.startswith("# lab/sim#7 Sim run diverges [open]")


def test_fetch_a_bare_number_needs_one_repo(run_cli, tmp_path):
    run_cli("init", "--repo", "org/repo", "--repo", "lab/sim")
    proc = run_cli("fetch", "issue", "2", scenario="fetch", check=False)
    assert proc.returncode == 2
    assert "ambiguous: #2 — use owner/name#2 (repos: org/repo, lab/sim)" in proc.stderr
    assert run_cli("fetch", "issue", "sim#7", scenario="fetch", check=False).returncode == 2
    assert run_cli("fetch", "issue", "lab/sim#7", scenario="fetch").stdout.startswith("# lab/sim#7 ")
