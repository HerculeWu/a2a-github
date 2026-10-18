import json
import tomllib

import pytest

from a2a.workspace import ConfigError, find_workspace, load_config


def test_init_detects_repo_and_login(run_cli, tmp_path):
    proc = run_cli("init")
    ws = tmp_path / ".a2a"
    cfg = tomllib.loads((ws / "config.toml").read_text())
    assert cfg["repos"] == ["org/repo"]
    assert "repo" not in cfg
    assert cfg["login"] == "me-bot"
    assert cfg["me"] == "me-bot"
    assert cfg["notify"]["path"] == ".a2a/notify.log"
    assert (ws / ".gitignore").read_text().strip() == "*"
    assert str(ws) in proc.stdout


def test_init_json_and_refuses_to_overwrite(run_cli, tmp_path):
    data = json.loads(run_cli("init", "--json").stdout)
    assert data["workspace"].endswith(".a2a")
    assert data["repos"] == ["org/repo"]
    again = run_cli("init", check=False)
    assert again.returncode == 1
    assert "exists" in again.stderr
    assert run_cli("init", "--force").returncode == 0


def test_init_shared_login_warns_when_me_is_a_real_user(run_cli, tmp_path):
    proc = run_cli("init", "--me", "taken-name")
    assert "taken-name" in proc.stderr and "real GitHub user" in proc.stderr
    cfg = tomllib.loads((tmp_path / ".a2a" / "config.toml").read_text())
    assert cfg["me"] == "taken-name" and cfg["login"] == "me-bot"


def test_init_respects_dir(run_cli, tmp_path):
    run_cli("init", "--dir", str(tmp_path / "agent-x"))
    cfg = tomllib.loads((tmp_path / "agent-x" / "config.toml").read_text())
    assert cfg["notify"]["path"] == "agent-x/notify.log"


def test_find_workspace_walks_up(tmp_a2a_dir, monkeypatch):
    sub = tmp_a2a_dir.parent / "a" / "b"
    sub.mkdir(parents=True)
    monkeypatch.delenv("A2A_DIR", raising=False)
    assert find_workspace(cwd=sub) == tmp_a2a_dir
    monkeypatch.setenv("A2A_DIR", str(sub))
    assert find_workspace(cwd=sub) == sub
    assert find_workspace(explicit=str(tmp_a2a_dir), cwd=sub) == tmp_a2a_dir


def test_find_workspace_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("A2A_DIR", raising=False)
    try:
        find_workspace(cwd=tmp_path)
    except ConfigError as e:
        assert "a2a init" in str(e)
    else:
        raise AssertionError("expected ConfigError")


def test_load_config_defaults_and_warnings(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('repos = ["o/r"]\nlogin = "acct"\nme = "agent-x"\n[filters]\nassignee = true\n')
    cfg, warnings = load_config(p)
    assert cfg.filters.ignore_self is True
    assert cfg.filters.labels == []
    assert cfg.watch.interval == 60
    assert cfg.notify.sink == "stdout"
    assert cfg.shared_login
    assert any("assignee" in w for w in warnings)


def test_load_config_rejects_bad_values(tmp_path):
    p = tmp_path / "config.toml"
    for body in [
        'repos = ["noslash"]\nme = "x"\n',
        'repos = []\nme = "x"\n',
        'repos = "o/r"\nme = "x"\n',
        'repos = ["o/r", "O/R"]\nme = "x"\n',
        'me = "x"\n',
        'repos = ["o/r"]\nme = "bad name"\n',
        'repos = ["o/r"]\nme = "x"\n[filters]\ntitle_regex = "("\n',
        'repos = ["o/r"]\nme = "x"\n[notify]\nsink = "pigeon"\n',
        'repos = ["o/r"]\nme = "x"\n[notify]\nsink = "command"\n',
        "not toml = = =",
    ]:
        p.write_text(body)
        try:
            load_config(p)
        except ConfigError:
            continue
        raise AssertionError(f"accepted: {body!r}")


def test_init_shared_login_disables_assignee(run_cli, tmp_path):
    run_cli("init", "--me", "agent-x")
    cfg = tomllib.loads((tmp_path / ".a2a" / "config.toml").read_text())
    assert cfg["filters"]["assignee"] is False
    assert cfg["filters"]["labels"] == ["pin:agent-x"]
    assert "assignee" not in run_cli("state", "dump").stderr


def test_init_own_account_keeps_assignee(run_cli, tmp_path):
    run_cli("init")
    cfg = tomllib.loads((tmp_path / ".a2a" / "config.toml").read_text())
    assert cfg["filters"]["assignee"] is True


def test_load_config_keeps_every_repo_in_order(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('repos = ["lab/paper", "lab/sim"]\nme = "x"\n')
    cfg, warnings = load_config(p)
    assert cfg.repos == ["lab/paper", "lab/sim"]
    assert warnings == []


def test_load_config_rejects_a_01_repo_with_the_fix_line(tmp_path):
    p = tmp_path / "config.toml"
    for body in ('repo = "lab/paper"\nme = "x"\n', 'repo = "lab/paper"\nrepos = ["lab/paper"]\nme = "x"\n'):
        p.write_text(body)
        with pytest.raises(ConfigError) as e:
            load_config(p)
        assert str(e.value) == 'repo was replaced by repos; write repos = ["lab/paper"]'


def test_load_config_warns_on_unknown_filter_keys(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('repos = ["lab/paper"]\nme = "x"\n[filters]\nlables = ["a"]\n[filters."lab/sim"]\nlabels = ["b"]\n')
    cfg, warnings = load_config(p)
    assert cfg.filters.labels == []
    assert warnings == [
        "unknown key filters.lables ignored; filters apply to every repository in repos",
        'unknown key filters."lab/sim" ignored; filters apply to every repository in repos',
    ]


def test_init_writes_every_repo_given(run_cli, tmp_path):
    data = json.loads(run_cli("init", "--repo", "lab/paper", "--repo", "lab/sim", "--json").stdout)
    assert data["repos"] == ["lab/paper", "lab/sim"]
    cfg = tomllib.loads((tmp_path / ".a2a" / "config.toml").read_text())
    assert cfg["repos"] == ["lab/paper", "lab/sim"]
    assert "lab/paper, lab/sim" in run_cli("init", "--force", "--repo", "lab/paper", "--repo", "lab/sim").stdout


def test_init_rejects_a_malformed_repo(run_cli, tmp_path):
    proc = run_cli("init", "--repo", "lab", check=False)
    assert proc.returncode == 1
    assert not (tmp_path / ".a2a" / "config.toml").exists()

