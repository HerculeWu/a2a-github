"""Inbox: append-only `inbox.jsonl` plus Read state in `acks.json` (ADR-0005)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from a2a import fsio
from a2a.text import truncate_display
from a2a.timeutil import fmt_short, parse_iso

LIST_SNIPPET_COLS = 60
MIN_TYPE_COL = 8


class InboxError(Exception):
    pass


class InboxStore:
    def __init__(self, inbox_path: Path, acks_path: Path):
        self.inbox_path = Path(inbox_path)
        self.acks_path = Path(acks_path)

    def entries(self) -> list[dict]:
        return fsio.read_jsonl(self.inbox_path)

    def acked(self) -> set[str]:
        return set(fsio.read_json(self.acks_path, {"ids": []}).get("ids", []))

    def append(self, entries: Iterable[dict]) -> int:
        """Append entries whose id is not already present; returns how many were added."""
        with fsio.locked(self.inbox_path.with_name("inbox-dedupe")):
            existing = {e["id"] for e in self.entries()}
            fresh = []
            for e in entries:
                if e["id"] not in existing:
                    existing.add(e["id"])
                    fresh.append({k: v for k, v in e.items() if k != "read"})
            fsio.append_jsonl(self.inbox_path, fresh)
        return len(fresh)

    def list(
        self,
        unread: bool = False,
        since: str | None = None,
        types: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        acked = self.acked()
        since_dt = parse_iso(since) if since else None
        out = []
        for e in self.entries():
            read = e["id"] in acked
            if unread and read:
                continue
            if types and e.get("type") not in types:
                continue
            if since_dt and parse_iso(e["ts"]) < since_dt:
                continue
            out.append({**e, "read": read})
        if limit is not None:
            out = out[-limit:] if limit > 0 else []
        return out

    def count(self, unread: bool = False) -> int:
        return len(self.list(unread=unread))

    def ack(self, targets: Iterable[str] = (), all_: bool = False) -> list[str]:
        """Mark entries Read by id, `#number`, or all; returns the ids newly acked."""
        entries = self.entries()
        if all_:
            wanted = [e["id"] for e in entries]
        else:
            wanted = []
            for t in targets:
                if t.startswith("#"):
                    try:
                        number = int(t[1:])
                    except ValueError as err:
                        raise InboxError(f"not a thread number: {t!r}") from err
                    # A Thread may simply have no entries yet, so `#N` never errors.
                    ids = [e["id"] for e in entries if e.get("number") == number]
                else:
                    ids = [e["id"] for e in entries if e["id"] == t]
                    if not ids:
                        raise InboxError(f"no inbox entry matches {t!r}")
                wanted.extend(ids)
        with fsio.locked(self.acks_path):
            acked = self.acked()
            new = [i for i in dict.fromkeys(wanted) if i not in acked]
            if new:
                fsio.atomic_write_json(self.acks_path, {"ids": sorted(acked | set(new))})
        return new


def format_lines(entries: list[dict]) -> list[str]:
    """Fixed-format, column-aligned one-line-per-entry view."""
    if not entries:
        return []
    nums = [f"#{e['number']}" for e in entries]
    num_w = max(len(n) for n in nums)
    type_w = max(MIN_TYPE_COL, *(len(e["type"]) for e in entries))
    author_w = max(len(e.get("author", "")) for e in entries)
    lines = []
    for n, e in zip(nums, entries):
        cols = [
            n.ljust(num_w),
            e["type"].ljust(type_w),
            e.get("author", "").ljust(author_w),
            fmt_short(parse_iso(e["ts"])),
            truncate_display(e.get("snippet", ""), LIST_SNIPPET_COLS),
        ]
        lines.append("  ".join(cols).rstrip())
    return lines
