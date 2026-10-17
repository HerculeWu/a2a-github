import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bin_shim_runs_without_install(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "A2A_DIR")}
    proc = subprocess.run([str(ROOT / "bin" / "a2a"), "sign", "--as", "agent-x"], input="hi", capture_output=True,
                          text=True, cwd=tmp_path, env=env)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.endswith("<!-- a2a:from=agent-x -->\n")


def test_plugin_manifests_are_valid_json():
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert plugin["name"] == market["plugins"][0]["name"] == "a2a-github"
    assert (ROOT / "skills" / "a2a" / "SKILL.md").read_text().startswith("---\nname: a2a\n")
