import json


def test_watch_once_json_and_text(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    data = json.loads(run_cli("watch", "--once", "--backfill", "3650d", "--json", scenario="watch_a", cwd=cwd).stdout)
    assert len(data["new"]) == 7
    assert run_cli("watch", "--once", scenario="watch_a", cwd=cwd).stdout == "0\n"
    assert run_cli("watch", "--once", scenario="watch_b", cwd=cwd).stdout == "4\n"
    assert run_cli("inbox", "count", "--unread", cwd=cwd).stdout == "11\n"


def test_watch_reports_gh_errors(run_cli, tmp_a2a_dir):
    proc = run_cli("watch", "--once", scenario="basic", cwd=tmp_a2a_dir.parent, check=False)
    assert proc.returncode == 1
    assert "404" in proc.stderr


def test_watch_rejects_bad_backfill(run_cli, tmp_a2a_dir):
    proc = run_cli("watch", "--once", "--backfill", "soon", scenario="watch_a", cwd=tmp_a2a_dir.parent, check=False)
    assert proc.returncode == 1


def test_watch_once_exits_1_when_a_repo_fails_but_keeps_the_others(run_cli, tmp_path):
    run_cli("init", "--repo", "org/repo", "--repo", "org/missing")
    proc = run_cli("watch", "--once", "--backfill", "3650d", "--json", scenario="watch_multi", check=False)
    assert proc.returncode == 1
    assert "org/missing skipped this round" in proc.stderr
    assert {e["repo"] for e in json.loads(proc.stdout)["new"]} == {"org/repo"}
    assert run_cli("inbox", "count").stdout == "7\n"
