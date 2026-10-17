"""`a2a` command line: argument parsing, output (text or --json), error handling."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable

from a2a import __version__
from a2a.gh import GhError, make_gh
from a2a.inbox import InboxError, InboxStore, format_lines
from a2a.sign import sign
from a2a.timeutil import parse_duration
from a2a.watch import run_daemon, run_round, watch_lock
from a2a.state import StateStore, compact, format_value, parse_value
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


def cmd_state(app: App, args) -> Result:
    store = StateStore(app.workspace().state_path)
    if args.state_cmd == "get":
        try:
            value = store.get(args.key)
        except KeyError:
            return Result(code=1)
        return Result(text=format_value(value), data=value)
    if args.state_cmd == "set":
        value = parse_value(args.value, raw=args.raw)
        store.set(args.key, value)
        return Result(data={"key": args.key, "value": value})
    if args.state_cmd == "delete":
        return Result(data={"deleted": store.delete(args.key)})
    data = store.dump()
    return Result(text="\n".join(f"{k}={compact(v)}" for k, v in sorted(data.items())), data=data)


def inbox_store(app: App) -> InboxStore:
    ws = app.workspace()
    return InboxStore(ws.inbox_path, ws.acks_path)


def cmd_inbox(app: App, args) -> Result:
    store = inbox_store(app)
    if args.inbox_cmd == "list":
        types = [t.strip() for t in args.type.split(",") if t.strip()] if args.type else None
        entries = store.list(unread=args.unread, since=args.since, types=types, limit=args.limit)
        return Result(text="\n".join(format_lines(entries)), data=entries)
    if args.inbox_cmd == "count":
        n = store.count(unread=args.unread)
        return Result(text=str(n), data={"count": n})
    if not args.all and not args.targets:
        app.args._parser_ack.error("give entry ids, #numbers, or --all")
    new = store.ack(args.targets, all_=args.all)
    return Result(text=f"acked {len(new)}", data={"acked": new})


def cmd_sign(app: App, args) -> Result:
    name = args.as_name or app.config().me
    body = sign(sys.stdin.read(), name)
    return Result(text=body, data={"body": body})


def cmd_watch(app: App, args) -> Result:
    ws = app.workspace()
    cfg = app.config()
    backfill = parse_duration(args.backfill) if args.backfill else timedelta(0)
    try:
        with watch_lock(ws):
            if args.once:
                result = run_round(ws, cfg, app.gh, backfill=backfill, warn=app.warn)
                return Result(text=str(len(result.new)), data={"new": result.new})

            def on_round(result):
                if result.new:
                    emit(Result(text=str(len(result.new)), data={"new": result.new}), getattr(args, "json", False))
                    sys.stdout.flush()

            run_daemon(ws, cfg, app.gh, args.interval or cfg.watch.interval, on_round, backfill=backfill)
            return Result()
    except BlockingIOError as e:
        raise ConfigError(f"another `a2a watch` is already running for {ws.root}") from e


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

    p = sub.add_parser("state", parents=[common], help="flat JSON key-value store for your own bookkeeping")
    ssub = p.add_subparsers(dest="state_cmd", required=True, metavar="ACTION")
    g = ssub.add_parser("get", parents=[common], help="print a value (exit 1 if missing)")
    g.add_argument("key")
    st = ssub.add_parser("set", parents=[common], help="store a value: JSON if it parses, else a string")
    st.add_argument("key")
    st.add_argument("value")
    st.add_argument("--raw", action="store_true", help="always store VALUE as a string")
    d = ssub.add_parser("delete", parents=[common], help="remove a key (no error if absent)")
    d.add_argument("key")
    ssub.add_parser("dump", parents=[common], help="print every key")
    p.set_defaults(func=cmd_state)

    p = sub.add_parser("inbox", parents=[common], help="list, count and acknowledge matched activity")
    isub = p.add_subparsers(dest="inbox_cmd", required=True, metavar="ACTION")
    li = isub.add_parser("list", parents=[common], help="one line per entry, oldest first")
    li.add_argument("--unread", action="store_true", help="only entries not yet acked")
    li.add_argument("--since", metavar="ISO", help="only entries at or after this UTC time")
    li.add_argument("--type", metavar="T[,T]", help="only these activity types")
    li.add_argument("--limit", type=int, metavar="N", help="only the last N entries")
    co = isub.add_parser("count", parents=[common], help="print the number of entries")
    co.add_argument("--unread", action="store_true", help="count only unread entries")
    ack = isub.add_parser("ack", parents=[common], help="mark entries read")
    ack.add_argument("targets", nargs="*", metavar="ID|#N", help="entry id, or #N for every entry of thread N")
    ack.add_argument("--all", action="store_true", help="mark every entry read")
    ack.set_defaults(_parser_ack=ack)
    p.set_defaults(func=cmd_inbox)

    p = sub.add_parser("sign", parents=[common], help="append your signature to a body read from stdin")
    p.add_argument("--as", dest="as_name", metavar="NAME", help="sign as NAME (default: me from config)")
    p.set_defaults(func=cmd_sign)

    p = sub.add_parser("watch", parents=[common], help="poll the repository and append matching activity to the inbox")
    p.add_argument("--once", action="store_true", help="run a single round and exit (for cron and tests)")
    p.add_argument("--interval", type=int, metavar="SEC", help="seconds between rounds (default: watch.interval)")
    p.add_argument("--backfill", metavar="DURATION", help="on the first run, also consider activity this far back (e.g. 7d)")
    p.set_defaults(func=cmd_watch)

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
    except (ConfigError, GhError, InboxError, ValueError) as e:
        for w in app.warnings:
            print(f"a2a: warning: {w}", file=sys.stderr)
        print(f"a2a: error: {e}", file=sys.stderr)
        return 1
    for w in app.warnings:
        print(f"a2a: warning: {w}", file=sys.stderr)
    emit(result, getattr(args, "json", False))
    return result.code
