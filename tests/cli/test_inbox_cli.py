import json

from a2a.inbox import InboxStore


def seed(ws):
    InboxStore(ws / "inbox.jsonl", ws / "acks.json").append(
        [
            {"id": "c-1", "ts": "2026-10-17T17:40:00Z", "type": "comment", "repo": "org/repo", "number": 123, "author": "alice",
             "login": "alice", "title": "T", "snippet": "能不能改成这样", "url": "u", "matched_rules": ["mentions"]},
            {"id": "e-2", "ts": "2026-10-17T18:00:00Z", "type": "assigned", "repo": "org/repo", "number": 130, "author": "bob",
             "login": "bob", "title": "U", "snippet": "assignee: me-bot", "url": "u", "matched_rules": ["assignee"]},
        ]
    )


def test_inbox_list_count_ack(run_cli, tmp_a2a_dir):
    seed(tmp_a2a_dir)
    cwd = tmp_a2a_dir.parent
    assert run_cli("inbox", "list", cwd=cwd).stdout.splitlines() == [
        "org/repo#123  comment   alice  2026-10-17T17:40  能不能改成这样",
        "org/repo#130  assigned  bob    2026-10-17T18:00  assignee: me-bot",
    ]
    assert run_cli("inbox", "count", "--unread", cwd=cwd).stdout == "2\n"
    data = json.loads(run_cli("inbox", "list", "--json", cwd=cwd).stdout)
    assert [e["read"] for e in data] == [False, False]
    assert run_cli("inbox", "ack", "#123", cwd=cwd).stdout == "acked 1\n"
    assert run_cli("inbox", "list", "--unread", "--type", "comment,assigned", cwd=cwd).stdout.startswith("org/repo#130")
    assert json.loads(run_cli("inbox", "count", "--unread", "--json", cwd=cwd).stdout) == {"count": 1}
    assert json.loads(run_cli("inbox", "ack", "--all", "--json", cwd=cwd).stdout) == {"acked": ["e-2"]}
    assert run_cli("inbox", "list", "--unread", cwd=cwd).stdout == ""
    assert json.loads(run_cli("inbox", "list", "--unread", "--json", cwd=cwd).stdout) == []


def test_inbox_errors(run_cli, tmp_a2a_dir):
    seed(tmp_a2a_dir)
    cwd = tmp_a2a_dir.parent
    assert run_cli("inbox", "ack", "c-404", cwd=cwd, check=False).returncode == 1
    assert run_cli("inbox", "ack", cwd=cwd, check=False).returncode == 2
    assert run_cli("inbox", "list", "--since", "whenever", cwd=cwd, check=False).returncode == 1


def seed_two_repos(run_cli, ws):
    run_cli("init", "--force", "--repo", "lab/paper", "--repo", "lab/sim", cwd=ws.parent)
    InboxStore(ws / "inbox.jsonl", ws / "acks.json").append(
        [
            {"id": "c-5", "ts": "2026-10-17T17:00:00Z", "type": "comment", "number": 7, "author": "old",
             "login": "old", "title": "T", "snippet": "from 0.1", "url": "u", "matched_rules": ["mentions"]},
            {"id": "c-6", "ts": "2026-10-17T17:40:00Z", "type": "comment", "repo": "lab/sim", "number": 7,
             "author": "alice", "login": "alice", "title": "T", "snippet": "hi", "url": "u", "matched_rules": ["mentions"]},
            {"id": "c-7", "ts": "2026-10-17T17:41:00Z", "type": "comment", "repo": "lab/paper", "number": 7,
             "author": "bob", "login": "bob", "title": "T", "snippet": "yo", "url": "u", "matched_rules": ["mentions"]},
        ]
    )


def test_ack_a_thread_across_repos(run_cli, tmp_a2a_dir):
    seed_two_repos(run_cli, tmp_a2a_dir)
    cwd = tmp_a2a_dir.parent
    assert run_cli("inbox", "list", cwd=cwd).stdout.splitlines() == [
        "#7           comment   old    2026-10-17T17:00  from 0.1",
        "lab/sim#7    comment   alice  2026-10-17T17:40  hi",
        "lab/paper#7  comment   bob    2026-10-17T17:41  yo",
    ]
    assert json.loads(run_cli("inbox", "ack", "LAB/SIM#7", "--json", cwd=cwd).stdout) == {"acked": ["c-6"]}
    assert run_cli("inbox", "ack", "lab/db#7", cwd=cwd).stdout == "acked 0\n"
    assert run_cli("inbox", "ack", "lab/paper#99", cwd=cwd).stdout == "acked 0\n"
    data = json.loads(run_cli("inbox", "list", "--json", cwd=cwd).stdout)
    assert "repo" not in data[0]
    assert data[1]["repo"] == "lab/sim"


def test_a_bare_number_with_several_repos_is_a_usage_error(run_cli, tmp_a2a_dir):
    seed_two_repos(run_cli, tmp_a2a_dir)
    for token in ("#7", "7"):
        proc = run_cli("inbox", "ack", token, cwd=tmp_a2a_dir.parent, check=False)
        assert proc.returncode == 2
        assert proc.stderr == "a2a: error: ambiguous: #7 — use owner/name#7 (repos: lab/paper, lab/sim)\n"
    proc = run_cli("inbox", "ack", "sim#7", cwd=tmp_a2a_dir.parent, check=False)
    assert proc.returncode == 2


def test_inbox_commands_check_that_the_config_loads(run_cli, tmp_a2a_dir):
    config = tmp_a2a_dir / "config.toml"
    config.write_text(config.read_text().replace('repos = ["org/repo"]', 'repo = "org/repo"'))
    proc = run_cli("inbox", "count", cwd=tmp_a2a_dir.parent, check=False)
    assert proc.returncode == 1
    assert 'repo was replaced by repos; write repos = ["org/repo"]' in proc.stderr
