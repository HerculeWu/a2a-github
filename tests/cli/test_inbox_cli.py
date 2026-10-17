import json

from a2a.inbox import InboxStore


def seed(ws):
    InboxStore(ws / "inbox.jsonl", ws / "acks.json").append(
        [
            {"id": "c-1", "ts": "2026-10-17T17:40:00Z", "type": "comment", "number": 123, "author": "alice",
             "login": "alice", "title": "T", "snippet": "能不能改成这样", "url": "u", "matched_rules": ["mentions"]},
            {"id": "e-2", "ts": "2026-10-17T18:00:00Z", "type": "assigned", "number": 130, "author": "bob",
             "login": "bob", "title": "U", "snippet": "assignee: me-bot", "url": "u", "matched_rules": ["assignee"]},
        ]
    )


def test_inbox_list_count_ack(run_cli, tmp_a2a_dir):
    seed(tmp_a2a_dir)
    cwd = tmp_a2a_dir.parent
    assert run_cli("inbox", "list", cwd=cwd).stdout.splitlines() == [
        "#123  comment   alice  2026-10-17T17:40  能不能改成这样",
        "#130  assigned  bob    2026-10-17T18:00  assignee: me-bot",
    ]
    assert run_cli("inbox", "count", "--unread", cwd=cwd).stdout == "2\n"
    data = json.loads(run_cli("inbox", "list", "--json", cwd=cwd).stdout)
    assert [e["read"] for e in data] == [False, False]
    assert run_cli("inbox", "ack", "#123", cwd=cwd).stdout == "acked 1\n"
    assert run_cli("inbox", "list", "--unread", "--type", "comment,assigned", cwd=cwd).stdout.startswith("#130")
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
