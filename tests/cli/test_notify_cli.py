import json
import re
import sys

from a2a.inbox import InboxStore


def seed(ws, *ids):
    InboxStore(ws / "inbox.jsonl", ws / "acks.json").append(
        [{"id": i, "ts": "2026-10-17T10:00:00Z", "type": "comment", "number": n, "author": "alice", "snippet": "s"}
         for n, i in enumerate(ids, start=1)]
    )


def set_notify(ws, block):
    cfg = ws / "config.toml"
    text = re.sub(r"\[notify\].*", block, cfg.read_text(), flags=re.S)
    cfg.write_text(text)


def test_stdout_sink_and_no_repeat(run_cli, tmp_a2a_dir):
    set_notify(tmp_a2a_dir, '[notify]\nsink = "stdout"\n')
    cwd = tmp_a2a_dir.parent
    assert run_cli("notify", cwd=cwd).stdout == ""
    seed(tmp_a2a_dir, "c-1", "c-2")
    assert run_cli("notify", cwd=cwd).stdout == "inbox: 2 unread — #1 comment(alice), #2 comment(alice)\n"
    assert run_cli("notify", cwd=cwd).stdout == ""
    assert run_cli("notify", "--force", cwd=cwd).stdout.startswith("inbox: 2 unread")
    seed(tmp_a2a_dir, "c-1", "c-2", "c-3")
    data = json.loads(run_cli("notify", "--json", cwd=cwd).stdout)
    assert data == {"sent": True, "sink": "stdout", "unread": 3,
                    "digest": "inbox: 3 unread — #1 comment(alice), #2 comment(alice), #3 comment(alice)"}
    assert json.loads(run_cli("notify", "--json", cwd=cwd).stdout)["sent"] is False


def test_file_sink_appends(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    seed(tmp_a2a_dir, "c-1")
    assert run_cli("notify", cwd=cwd).stdout == ""
    seed(tmp_a2a_dir, "c-1", "c-2")
    run_cli("notify", cwd=cwd)
    lines = (tmp_a2a_dir / "notify.log").read_text().splitlines()
    assert lines == ["inbox: 1 unread — #1 comment(alice)", "inbox: 2 unread — #1 comment(alice), #2 comment(alice)"]


def test_command_sink_receives_stdin(run_cli, tmp_a2a_dir, tmp_path):
    out = tmp_path / "received.txt"
    script = "import sys; open(sys.argv[1], 'w').write(sys.stdin.read())"
    set_notify(tmp_a2a_dir, f"[notify]\nsink = \"command\"\ncommand = {json.dumps([sys.executable, '-c', script, str(out)])}\n")
    seed(tmp_a2a_dir, "c-1")
    run_cli("notify", cwd=tmp_a2a_dir.parent)
    assert out.read_text() == "inbox: 1 unread — #1 comment(alice)\n"


def test_command_sink_failure_is_reported_and_retried(run_cli, tmp_a2a_dir):
    set_notify(tmp_a2a_dir, f"[notify]\nsink = \"command\"\ncommand = {json.dumps([sys.executable, '-c', 'import sys; sys.exit(3)'])}\n")
    seed(tmp_a2a_dir, "c-1")
    cwd = tmp_a2a_dir.parent
    proc = run_cli("notify", cwd=cwd, check=False)
    assert proc.returncode == 1 and "exited 3" in proc.stderr
    # not marked as announced, so the stdout override still sends it
    assert run_cli("notify", "--sink", "stdout", cwd=cwd).stdout.startswith("inbox: 1 unread")


def test_sink_override_needs_config(run_cli, tmp_a2a_dir):
    seed(tmp_a2a_dir, "c-1")
    proc = run_cli("notify", "--sink", "command", cwd=tmp_a2a_dir.parent, check=False)
    assert proc.returncode == 1 and "notify.command" in proc.stderr


def test_watch_notify_runs_after_new_entries(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    run_cli("watch", "--once", "--backfill", "3650d", "--notify", scenario="watch_a", cwd=cwd)
    assert (tmp_a2a_dir / "notify.log").read_text().startswith("inbox: 7 unread — ")
