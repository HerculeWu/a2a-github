"""`a2a` command line: argument parsing, output (text or --json), error handling."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Callable

from a2a import __version__
from a2a.gh import GhError, make_gh
from a2a.workspace import ConfigError, Workspace, find_workspace, init_target, init_workspace


@dataclass
class Result:
    text: str | None = None
    data: Any = None
    code: int = 0


class App:
    """What a command needs from its environment; tests can swap any part."""

    def __init__(self, args: argparse.Namespace, gh_factory: Callable[[], Any] = make_gh):
        self.args = args
        self._gh_factory = gh_factory
        self._gh = None
        self.warnings: list[str] = []

    @property
    def gh(self):
        if self._gh is None:
            self._gh = self._gh_factory()
        return self._gh

    def workspace(self) -> Workspace:
        return Workspace(find_workspace(getattr(self.args, "dir", None)))

    def config(self):
        cfg, warnings = self.workspace().load()
        self.warnings.extend(warnings)
        return cfg

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def cmd_init(app: App, args) -> Result:
    gh = app.gh
    repo = args.repo
    if not repo:
        try:
            repo = gh.run("repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
        except GhError:
            repo = "org/repo"
            app.warn('could not detect the repository; edit "repo" in config.toml')
    try:
        login = gh.api("user").body["login"]
    except (GhError, KeyError, TypeError):
        login = args.me or "my-login"
        app.warn('could not detect the gh login; edit "login" in config.toml')
    me = args.me or login
    if me.lower() != login.lower():
        try:
            gh.api(f"users/{me}")
            app.warn(f"{me!r} is a real GitHub user: @{me} mentions will notify them; consider another name")
        except GhError:
            pass
    target = init_workspace(init_target(getattr(args, "dir", None)), repo=repo, login=login, me=me, force=args.force)
    data = {"workspace": str(target), "repo": repo, "login": login, "me": me}
    return Result(text=f"initialised {target} (repo {repo}, me {me})", data=data)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="machine-readable output")
    common.add_argument("--dir", default=argparse.SUPPRESS, help="workspace directory (default: nearest .a2a/)")

    parser = argparse.ArgumentParser(prog="a2a", parents=[common], description="GitHub collaboration primitives.")
    parser.add_argument("--version", action="version", version=f"a2a {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("init", parents=[common], help="create a workspace with a config template")
    p.add_argument("--repo", help="owner/name (default: detect with gh)")
    p.add_argument("--me", help="who this workspace acts for (default: the gh login)")
    p.add_argument("--force", action="store_true", help="overwrite an existing config")
    p.set_defaults(func=cmd_init)

    return parser


def emit(result: Result, as_json: bool, out=sys.stdout) -> None:
    if as_json:
        if result.data is not None:
            out.write(json.dumps(result.data, ensure_ascii=False) + "\n")
    elif result.text:
        out.write(result.text if result.text.endswith("\n") else result.text + "\n")


def main(argv: list[str] | None = None, gh_factory: Callable[[], Any] = make_gh) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    app = App(args, gh_factory)
    try:
        result = args.func(app, args)
    except (ConfigError, GhError, ValueError) as e:
        for w in app.warnings:
            print(f"a2a: warning: {w}", file=sys.stderr)
        print(f"a2a: error: {e}", file=sys.stderr)
        return 1
    for w in app.warnings:
        print(f"a2a: warning: {w}", file=sys.stderr)
    emit(result, getattr(args, "json", False))
    return result.code
