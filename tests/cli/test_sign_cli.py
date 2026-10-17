import json


def test_sign_uses_me_from_workspace(run_cli, tmp_a2a_dir):
    out = run_cli("sign", stdin="hello\n", cwd=tmp_a2a_dir.parent).stdout
    assert out == "hello\n\n<sub>— me-bot</sub>\n<!-- a2a:from=me-bot -->\n"


def test_sign_as_without_workspace(run_cli, tmp_path):
    out = run_cli("sign", "--as", "agent-y", "--json", stdin="x", cwd=tmp_path).stdout
    assert json.loads(out) == {"body": "x\n\n<sub>— agent-y</sub>\n<!-- a2a:from=agent-y -->"}


def test_sign_without_workspace_or_name_fails(run_cli, tmp_path):
    assert run_cli("sign", stdin="x", cwd=tmp_path, check=False).returncode == 1
