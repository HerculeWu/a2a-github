import json


def test_state_commands(run_cli, tmp_a2a_dir):
    cwd = tmp_a2a_dir.parent
    assert run_cli("state", "set", "phase", "reviewing", cwd=cwd).stdout == ""
    assert run_cli("state", "get", "phase", cwd=cwd).stdout == "reviewing\n"
    run_cli("state", "set", "n", '{"a": [1, "二"]}', cwd=cwd)
    assert run_cli("state", "get", "n", cwd=cwd).stdout == '{"a":[1,"二"]}\n'
    run_cli("state", "set", "flag", "true", "--raw", cwd=cwd)
    assert json.loads(run_cli("state", "get", "flag", "--json", cwd=cwd).stdout) == "true"
    assert run_cli("state", "dump", cwd=cwd).stdout.splitlines() == ['flag="true"', 'n={"a":[1,"二"]}', 'phase="reviewing"']
    assert json.loads(run_cli("state", "dump", "--json", cwd=cwd).stdout) == {"flag": "true", "n": {"a": [1, "二"]}, "phase": "reviewing"}
    run_cli("state", "delete", "phase", cwd=cwd)
    run_cli("state", "delete", "phase", cwd=cwd)
    missing = run_cli("state", "get", "phase", cwd=cwd, check=False)
    assert missing.returncode == 1 and missing.stdout == ""
    assert json.loads(run_cli("state", "delete", "n", "--json", cwd=cwd).stdout) == {"deleted": True}
    assert json.loads(run_cli("state", "set", "x", "1", "--json", cwd=cwd).stdout) == {"key": "x", "value": 1}


def test_no_workspace_is_an_error(run_cli, tmp_path):
    proc = run_cli("state", "dump", cwd=tmp_path, check=False)
    assert proc.returncode == 1
    assert "a2a init" in proc.stderr
