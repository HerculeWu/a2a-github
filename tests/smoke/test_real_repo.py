"""Round trip against a real sandbox repository. Opt in with A2A_TEST_REPO=org/sandbox.

Creates one issue, comments on it and closes it again, using the gh account you are logged in as.
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPO = os.environ.get("A2A_TEST_REPO")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not REPO, reason="set A2A_TEST_REPO=org/sandbox to run against a real repository"),
]


def a2a(ws, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("A2A_GH_FAKE", "A2A_GH_FAKE_DIR")}
    env.update(A2A_DIR=str(ws), PYTHONPATH=str(ROOT))
    proc = subprocess.run([sys.executable, "-m", "a2a", *args], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def wait_for(ws, predicate, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        a2a(ws, "watch", "--once")
        entries = json.loads(a2a(ws, "inbox", "list", "--json"))
        found = [e for e in entries if predicate(e)]
        if found:
            return found
        time.sleep(10)
    raise AssertionError("activity never reached the inbox")


def test_issue_and_comment_reach_the_inbox(tmp_path):
    token = f"a2a-smoke-{uuid.uuid4().hex[:8]}"
    ws = tmp_path / ".a2a"
    a2a(ws, "init", "--repo", REPO)
    cfg = ws / "config.toml"
    text = cfg.read_text()
    text = re.sub(r'title_regex = ""', f'title_regex = "{token}"', text)
    text = re.sub(r"ignore_self = true", "ignore_self = false", text)  # the test account is also me
    cfg.write_text(text)
    a2a(ws, "watch", "--once")  # baseline: observe from now

    url = gh("issue", "create", "--repo", REPO, "--title", f"{token} smoke test", "--body", "created by a2a smoke test").strip()
    number = int(url.rstrip("/").rsplit("/", 1)[1])
    try:
        opened = wait_for(ws, lambda e: e["number"] == number and e["type"] == "issue_opened")
        assert opened[0]["matched_rules"] == ["title_regex"]

        gh("issue", "comment", str(number), "--repo", REPO, "--body", "smoke comment")
        comment = wait_for(ws, lambda e: e["number"] == number and e["type"] == "comment")
        assert comment[0]["snippet"] == "smoke comment"
        assert "smoke comment" in a2a(ws, "fetch", "issue", str(number))
    finally:
        gh("issue", "close", str(number), "--repo", REPO)
