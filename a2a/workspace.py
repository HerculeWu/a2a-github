"""Workspace discovery, config loading/validation, and the `init` template."""

from __future__ import annotations

import json
import os
import re
import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DIR_NAME = ".a2a"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
SINKS = ("stdout", "file", "command")
FILTER_KEYS = frozenset({
    "assignee", "mentions", "mention_aliases", "participated", "labels",
    "title_regex", "body_regex", "ignore_self", "exclude_authors",
})
BARE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ConfigError(Exception):
    pass


@dataclass
class Filters:
    assignee: bool = False
    mentions: bool = False
    mention_aliases: list[str] = field(default_factory=list)
    participated: bool = False
    labels: list[str] = field(default_factory=list)
    title_regex: str = ""
    body_regex: str = ""
    ignore_self: bool = True
    exclude_authors: list[str] = field(default_factory=list)


@dataclass
class WatchConfig:
    interval: int = 60


@dataclass
class NotifyConfig:
    sink: str = "stdout"
    path: str | None = None
    command: list[str] | None = None

    def require(self, sink: str) -> None:
        if sink == "file" and not self.path:
            raise ConfigError('sink "file" needs notify.path in config.toml')
        if sink == "command" and not self.command:
            raise ConfigError('sink "command" needs notify.command in config.toml')


@dataclass
class Config:
    repos: list[str]
    me: str
    login: str
    filters: Filters = field(default_factory=Filters)
    watch: WatchConfig = field(default_factory=WatchConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)

    @property
    def shared_login(self) -> bool:
        """Several Participants share one Login exactly when Me differs from it (ADR-0007)."""
        return self.me.lower() != self.login.lower()


@dataclass
class Workspace:
    root: Path

    @property
    def config_path(self) -> Path:
        return self.root / "config.toml"

    @property
    def inbox_path(self) -> Path:
        return self.root / "inbox.jsonl"

    @property
    def acks_path(self) -> Path:
        return self.root / "acks.json"

    @property
    def seen_path(self) -> Path:
        return self.root / "seen.json"

    @property
    def etags_path(self) -> Path:
        return self.root / "etags.json"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def notify_state_path(self) -> Path:
        return self.root / "notify.json"

    @property
    def watch_lock_path(self) -> Path:
        return self.root / "watch"

    def resolve(self, relative: str) -> Path:
        """Config paths are relative to the directory that contains the Workspace."""
        p = Path(relative).expanduser()
        return p if p.is_absolute() else self.root.parent / p

    def load(self) -> tuple[Config, list[str]]:
        return load_config(self.config_path)


def find_workspace(explicit: str | None = None, cwd: Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("A2A_DIR")
    if env:
        return Path(env).expanduser().resolve()
    here = (cwd or Path.cwd()).resolve()
    for d in (here, *here.parents):
        candidate = d / DIR_NAME
        if (candidate / "config.toml").is_file():
            return candidate
    raise ConfigError("no a2a workspace found (looked for .a2a/ upward); run `a2a init`")


def init_target(explicit: str | None = None, cwd: Path | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("A2A_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return (cwd or Path.cwd()).resolve() / DIR_NAME


def _str_list(value, key: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{key} must be a list of strings")
    return list(value)


def _bool(value, key: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be true or false")
    return value


def _repos(raw: dict) -> list[str]:
    if "repo" in raw:
        old = raw["repo"]
        example = json.dumps([old] if isinstance(old, str) else raw.get("repos", ["owner/name"]))
        raise ConfigError(f"repo was replaced by repos; write repos = {example}")
    repos = raw.get("repos")
    if not isinstance(repos, list) or not repos:
        raise ConfigError('repos must be a non-empty list like ["owner/name"]')
    seen: set[str] = set()
    for repo in repos:
        if not isinstance(repo, str) or not REPO_RE.match(repo):
            raise ConfigError(f'every entry in repos must look like "owner/name", got {repo!r}')
        if repo.casefold() in seen:
            raise ConfigError(f"repos lists {repo!r} twice")
        seen.add(repo.casefold())
    return list(repos)


def _toml_key(key: str) -> str:
    return key if BARE_KEY_RE.match(key) else json.dumps(key)


def load_config(path: Path) -> tuple[Config, list[str]]:
    try:
        raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ConfigError(f"missing config: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"invalid TOML in {path}: {e}") from e

    repos, me = _repos(raw), raw.get("me")
    if not isinstance(me, str) or not NAME_RE.match(me):
        raise ConfigError(f"me must match {NAME_RE.pattern}, got {me!r}")
    login = raw.get("login", me)
    if not isinstance(login, str) or not NAME_RE.match(login):
        raise ConfigError(f"login must match {NAME_RE.pattern}, got {login!r}")

    f = raw.get("filters", {})
    warnings = [
        f"unknown key filters.{_toml_key(key)} ignored; filters apply to every repository in repos"
        for key in f
        if key not in FILTER_KEYS
    ]
    filters = Filters()
    for key in ("assignee", "mentions", "participated", "ignore_self"):
        if key in f:
            setattr(filters, key, _bool(f[key], f"filters.{key}"))
    for key in ("mention_aliases", "labels", "exclude_authors"):
        if key in f:
            setattr(filters, key, _str_list(f[key], f"filters.{key}"))
    for key in ("title_regex", "body_regex"):
        value = f.get(key, "")
        if not isinstance(value, str):
            raise ConfigError(f"filters.{key} must be a string")
        try:
            re.compile(value)
        except re.error as e:
            raise ConfigError(f"filters.{key} is not a valid regex: {e}") from e
        setattr(filters, key, value)

    w = raw.get("watch", {})
    interval = w.get("interval", 60)
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
        raise ConfigError("watch.interval must be a positive integer (seconds)")

    n = raw.get("notify", {})
    sink = n.get("sink", "stdout")
    if sink not in SINKS:
        raise ConfigError(f"notify.sink must be one of {', '.join(SINKS)}, got {sink!r}")
    notify = NotifyConfig(sink=sink)
    if "path" in n:
        if not isinstance(n["path"], str) or not n["path"]:
            raise ConfigError("notify.path must be a non-empty string")
        notify.path = n["path"]
    if "command" in n:
        command = shlex.split(n["command"]) if isinstance(n["command"], str) else n["command"]
        if not command or not isinstance(command, list) or not all(isinstance(c, str) for c in command):
            raise ConfigError("notify.command must be a non-empty list or string")
        notify.command = command
    notify.require(sink)

    cfg = Config(repos=repos, me=me, login=login, filters=filters, watch=WatchConfig(interval), notify=notify)
    if cfg.shared_login and filters.assignee:
        warnings.append(
            f"filters.assignee matches every Participant sharing login {login!r}; "
            f'consider labels = ["pin:{me}"] instead'
        )
    return cfg, warnings


TEMPLATE = """\
repos = {repos}         # one or more owner/name to observe
login = {login}              # the GitHub account gh is authenticated as
me = {me}                 # = login for an own account; an agent name under a shared login

[filters]
assignee = {assignee}{assignee_note}
mentions = true
mention_aliases = []         # extra literal strings that address me, e.g. ["{me_raw}:"]
participated = true
labels = [{label}]
title_regex = ""
body_regex = ""
ignore_self = true           # never deliver activity whose author is me
exclude_authors = []         # glob patterns (* and ?), e.g. ["*[bot]"]

[watch]
interval = 60

[notify]
sink = "file"                # stdout | file | command
path = {notify_path}
# command = ["notify-send", "a2a"]   # for sink = "command": receives the digest on stdin
"""


def render_template(repos: list[str], login: str, me: str, notify_path: str) -> str:
    q = json.dumps  # TOML basic strings accept JSON string escapes
    shared = me.lower() != login.lower()  # every Participant on a shared login would match assignee
    return TEMPLATE.format(
        repos=q(repos), login=q(login), me=q(me), me_raw=me, label=q(f"pin:{me}"), notify_path=q(notify_path),
        assignee="false" if shared else "true",
        assignee_note="             # shared login: assignments name the login, so use labels" if shared else "",
    )


def init_workspace(target: Path, repos: list[str], login: str, me: str, force: bool = False) -> Path:
    target = Path(target)
    config_path = target / "config.toml"
    if config_path.exists() and not force:
        raise ConfigError(f"{config_path} already exists (use --force to overwrite)")
    _repos({"repos": repos})
    for key, value in (("me", me), ("login", login)):
        if not NAME_RE.match(value):
            raise ConfigError(f"{key} must match {NAME_RE.pattern}, got {value!r}")
    target.mkdir(parents=True, exist_ok=True)
    config_path.write_text(render_template(repos, login, me, f"{target.name}/notify.log"), encoding="utf-8")
    (target / ".gitignore").write_text("*\n", encoding="utf-8")
    return target
