#!/usr/bin/env bash
# Point the installed Claude Code plugin at this checkout, so edits here take
# effect without reinstalling. Re-run after `claude plugin update`, a reinstall,
# or a version bump in .claude-plugin/plugin.json: each of those re-copies the
# plugin into the cache and replaces the symlink.
set -euo pipefail

PLUGIN="a2a-github@a2a-github"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGINS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins"
CACHE_DIR="$PLUGINS_DIR/cache"
REGISTRY="$PLUGINS_DIR/installed_plugins.json"

install_path() {
  [[ -f "$REGISTRY" ]] || return 0
  python3 - "$REGISTRY" "$PLUGIN" <<'EOF'
import json, sys
entries = json.load(open(sys.argv[1])).get("plugins", {}).get(sys.argv[2], [])
for entry in entries:
    if entry.get("scope") == "user":
        print(entry["installPath"])
        break
EOF
}

path="$(install_path)"
if [[ -z "$path" ]]; then
  echo "Installing $PLUGIN from $REPO ..."
  claude plugin marketplace add "$REPO" >/dev/null 2>&1 || true
  claude plugin install "$PLUGIN" --scope user
  path="$(install_path)"
  [[ -n "$path" ]] || { echo "error: $PLUGIN not found in $REGISTRY after install" >&2; exit 1; }
fi

case "$path" in
  "$CACHE_DIR"/*) ;;
  *) echo "error: refusing to replace $path: not under $CACHE_DIR" >&2; exit 1 ;;
esac

if [[ -L "$path" && "$(readlink -f "$path")" == "$REPO" ]]; then
  echo "Already linked: $path -> $REPO"
  exit 0
fi

rm -rf "$path"
mkdir -p "$(dirname "$path")"
ln -s "$REPO" "$path"
echo "Linked: $path -> $REPO"
echo "Restart Claude Code to pick up the change."
