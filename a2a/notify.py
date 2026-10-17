"""Notify: push a one-line Digest of unread Inbox Entries to a Sink."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from a2a import fsio
from a2a.activity import TEXT_TYPES
from a2a.inbox import InboxStore
from a2a.workspace import Config, ConfigError, Workspace

DIGEST_ITEMS = 5
COMMAND_TIMEOUT = 30


class NotifyError(Exception):
    pass


def digest(unread: list[dict]) -> str:
    shown = unread[-DIGEST_ITEMS:]
    parts = [
        f"#{e['number']} {e['type']}({e.get('author', '')})" if e["type"] in TEXT_TYPES else f"#{e['number']} {e['type']}"
        for e in shown
    ]
    if len(unread) > len(shown):
        parts.append(f"+{len(unread) - len(shown)} more")
    return f"inbox: {len(unread)} unread — " + ", ".join(parts)


def has_unannounced(entries: list[dict], unread: list[dict], last_announced: str | None) -> bool:
    """True when some unread entry was appended after the last one already announced."""
    if not unread:
        return False
    order = {e["id"]: i for i, e in enumerate(entries)}
    mark = order.get(last_announced, -1) if last_announced else -1
    return any(order.get(e["id"], -1) > mark for e in unread)


@dataclass
class Outcome:
    sent: bool
    sink: str
    digest: str | None
    unread: int


def deliver(text: str, sink: str, cfg: Config, ws: Workspace) -> None:
    if sink == "file":
        path = ws.resolve(cfg.notify.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with fsio.locked(path), open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    elif sink == "command":
        try:
            proc = subprocess.run(cfg.notify.command, input=text + "\n", text=True, capture_output=True,
                                  timeout=COMMAND_TIMEOUT)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise NotifyError(f"notify command failed: {e}") from e
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip().splitlines()[-1:] or [""]
            raise NotifyError(f"notify command exited {proc.returncode} {detail[0]}".rstrip())


def notify(ws: Workspace, cfg: Config, sink: str | None = None, force: bool = False) -> Outcome:
    sink = sink or cfg.notify.sink
    try:
        cfg.notify.require(sink)
    except ConfigError as e:
        raise NotifyError(str(e)) from e
    store = InboxStore(ws.inbox_path, ws.acks_path)
    entries = store.list()
    unread = [e for e in entries if not e["read"]]
    last = fsio.read_json(ws.notify_state_path, {}).get("last_announced")
    if not unread or not (force or has_unannounced(entries, unread, last)):
        return Outcome(False, sink, None, len(unread))
    text = digest(unread)
    if sink != "stdout":
        deliver(text, sink, cfg, ws)
    fsio.atomic_write_json(ws.notify_state_path, {"last_announced": unread[-1]["id"]})
    return Outcome(True, sink, text, len(unread))
