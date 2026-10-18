import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from a2a.fake_gh import FakeGhClient
from a2a.workspace import init_workspace

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def tmp_a2a_dir(tmp_path):
    """An initialised Workspace for repo `org/repo`, Me = Login = `me-bot`."""
    ws = tmp_path / ".a2a"
    init_workspace(ws, repos=["org/repo"], login="me-bot", me="me-bot")
    return ws


@pytest.fixture
def fake_gh():
    """Factory: fake_gh("scenario") -> FakeGhClient replaying tests/fixtures/scenario."""

    def make(scenario=None, routes=None, commands=None):
        if scenario is not None:
            return FakeGhClient.from_dir(FIXTURES / scenario)
        return FakeGhClient(routes or {}, commands or {})

    return make


@pytest.fixture
def run_cli(tmp_path):
    """Run the real `a2a` CLI in a subprocess with the fake gh enabled."""

    def run(*args, scenario="basic", stdin=None, env=None, cwd=None, check=True):
        full_env = {
            **os.environ,
            "A2A_GH_FAKE": "1",
            "A2A_GH_FAKE_DIR": str(FIXTURES / scenario),
            "PYTHONPATH": str(ROOT),
        }
        full_env.pop("A2A_DIR", None)
        full_env.update(env or {})
        proc = subprocess.run(
            [sys.executable, "-m", "a2a", *args],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=cwd or tmp_path,
            env=full_env,
        )
        if check and proc.returncode != 0:
            raise AssertionError(f"a2a {' '.join(args)} exited {proc.returncode}: {proc.stderr}")
        return proc

    return run


def load_fixture(scenario, name="routes.json"):
    return json.loads((FIXTURES / scenario / name).read_text())
