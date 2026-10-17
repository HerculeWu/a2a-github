"""Watch Rounds: poll fixed URLs with ETags, normalize, filter, append to the Inbox (ADR-0004, ADR-0006)."""

from __future__ import annotations

import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable
from urllib.parse import urlencode

from a2a import fsio
from a2a.activity import (
    Activity,
    Thread,
    from_comment,
    from_event,
    from_review,
    opened_from_issue,
    thread_from_issue,
    to_entry,
)
from a2a.filters import evaluate
from a2a.gh import GhError
from a2a.inbox import InboxStore
from a2a.timeutil import fmt_iso, now as utc_now, parse_iso
from a2a.workspace import Config, Workspace

# Items this close below a cursor are re-examined; Seen ids resolve the overlap.
SLACK = timedelta(minutes=10)
MAX_PAGES = 30
MAX_BACKOFF = 15 * 60


def stream_urls(repo: str) -> dict[str, str]:
    return {
        "issues": f"repos/{repo}/issues?state=all&sort=updated&direction=desc&per_page=100",
        "comments": f"repos/{repo}/issues/comments?sort=updated&direction=desc&per_page=100",
        "review_comments": f"repos/{repo}/pulls/comments?sort=updated&direction=desc&per_page=100",
        "events": f"repos/{repo}/issues/events?per_page=100",
    }


# Which timestamp each stream is ordered by (newest first).
ORDER_KEY = {"issues": "updated_at", "comments": "updated_at", "review_comments": "updated_at", "events": "created_at"}


# Inbox id prefix -> the stream whose cursor bounds it.
ID_STREAM = {"i": "issues", "c": "comments", "e": "events", "r": "reviews"}


@dataclass
class RoundResult:
    new: list[dict] = field(default_factory=list)
    poll_interval: int | None = None


class Seen:
    """Per-stream cursors, ids near them, and Participated Threads (`seen.json`)."""

    def __init__(self, data: dict):
        self.cursors: dict[str, datetime] = {k: parse_iso(v) for k, v in data.get("cursors", {}).items()}
        self.recent: dict[str, str] = dict(data.get("recent", {}))
        self.participated: set[int] = set(data.get("participated", []))
        self.initialized_at: str | None = data.get("initialized_at")

    @classmethod
    def first_run(cls, start: datetime, at: datetime) -> "Seen":
        seen = cls({})
        seen.cursors = {name: start for name in (*ORDER_KEY, "reviews")}
        seen.initialized_at = fmt_iso(at)
        return seen

    def floor(self, stream: str) -> datetime:
        return self.cursors[stream] - SLACK

    def is_new(self, a: Activity, stream: str) -> bool:
        return a.ts >= self.floor(stream) and a.id not in self.recent

    def to_json(self) -> dict:
        # An id only matters while it is at or above its own stream's floor.
        recent = {
            i: ts
            for i, ts in self.recent.items()
            if parse_iso(ts) >= self.floor(ID_STREAM.get(i.split("-", 1)[0], "issues"))
        }
        return {
            "version": 1,
            "initialized_at": self.initialized_at,
            "cursors": {k: fmt_iso(v) for k, v in sorted(self.cursors.items())},
            "recent": dict(sorted(recent.items())),
            "participated": sorted(self.participated),
        }


def _poll_interval(resp) -> int | None:
    try:
        return int(resp.headers.get("x-poll-interval", ""))
    except ValueError:
        return None


def _page_on(gh, first, stream: str, floor: datetime) -> list[dict]:
    """The probe's items plus following pages, until items fall below `floor`."""
    items = list(first.body or [])
    next_url, pages = first.next_url, 1
    key = ORDER_KEY[stream]
    while next_url and items and parse_iso(items[-1][key]) >= floor and pages < MAX_PAGES:
        resp = gh.api(next_url)
        items.extend(resp.body or [])
        next_url, pages = resp.next_url, pages + 1
    return items


def _bootstrap_participation(gh, cfg: Config) -> set[int]:
    numbers: set[int] = set()
    for qualifier in ("author", "commenter", "reviewed-by"):
        path = "search/issues?" + urlencode({"q": f"repo:{cfg.repo} {qualifier}:{cfg.login}", "per_page": 100})
        resp = gh.api(path)
        numbers.update(item["number"] for item in (resp.body or {}).get("items", []))
    return numbers


def run_round(
    ws: Workspace,
    cfg: Config,
    gh,
    now: datetime | None = None,
    backfill: timedelta = timedelta(0),
    warn: Callable[[str], None] = lambda m: None,
) -> RoundResult:
    now = now or utc_now()
    urls = stream_urls(cfg.repo)
    etags: dict[str, str] = fsio.read_json(ws.etags_path, {})

    probes = {name: gh.api(url, etag=etags.get(url)) for name, url in urls.items()}
    intervals = [i for i in (_poll_interval(r) for r in probes.values()) if i]
    result = RoundResult(poll_interval=max(intervals) if intervals else None)
    if all(r.not_modified for r in probes.values()):
        return result

    seen_data = fsio.read_json(ws.seen_path, None)
    first_run = seen_data is None
    seen = Seen.first_run(now - backfill, now) if first_run else Seen(seen_data)

    items = {
        name: [] if resp.not_modified else _page_on(gh, resp, name, seen.floor(name)) for name, resp in probes.items()
    }

    threads: dict[int, Thread] = {}
    activities: list[tuple[Activity, str]] = []
    review_check: set[int] = set()
    inline_by_review: dict[int, list[dict]] = {}
    new_cursor = dict(seen.cursors)

    def advance(stream: str, ts: str) -> None:
        new_cursor[stream] = max(new_cursor[stream], parse_iso(ts))

    for item in items["issues"]:
        threads[item["number"]] = thread_from_issue(item)
        advance("issues", item["updated_at"])
        activities.append((opened_from_issue(item), "issues"))
        if "pull_request" in item and parse_iso(item["updated_at"]) >= seen.floor("issues"):
            review_check.add(item["number"])
    for item in items["comments"]:
        advance("comments", item["updated_at"])
        activities.append((from_comment(item), "comments"))
    for item in items["review_comments"]:
        advance("review_comments", item["updated_at"])
        if parse_iso(item["created_at"]) >= seen.floor("review_comments"):
            number = int(item["pull_request_url"].rstrip("/").rsplit("/", 1)[1])
            review_check.add(number)
            inline_by_review.setdefault(item.get("pull_request_review_id"), []).append(item)
    for item in items["events"]:
        advance("events", item["created_at"])
        a = from_event(item)
        if a is not None:
            activities.append((a, "events"))
            threads.setdefault(a.number, thread_from_issue(item["issue"]))
    for number in sorted(review_check):
        path = f"repos/{cfg.repo}/pulls/{number}/reviews?per_page=100"
        resp = gh.api(path)
        reviews = list(resp.body or [])
        while resp.next_url:
            resp = gh.api(resp.next_url)
            reviews.extend(resp.body or [])
        for r in reviews:
            inline = sorted(inline_by_review.get(r["id"], []), key=lambda c: c["created_at"])
            a = from_review(r, number, inline)
            if a is not None:
                advance("reviews", r["submitted_at"])
                activities.append((a, "reviews"))

    fresh = sorted((a for a, stream in activities if seen.is_new(a, stream)), key=lambda a: a.sort_key)

    if first_run and cfg.filters.participated and not cfg.shared_login:
        try:
            seen.participated |= _bootstrap_participation(gh, cfg)
        except GhError as e:
            warn(f"could not bootstrap participated threads from search: {e}")

    entries = []
    for a in fresh:
        if a.number not in threads:
            threads[a.number] = thread_from_issue(gh.api(f"repos/{cfg.repo}/issues/{a.number}").body)
        thread = threads[a.number]
        decision = evaluate(a, thread, seen.participated, cfg)
        if decision.delivered:
            entries.append(to_entry(a, thread, decision.matched))
        if a.type in ("issue_opened", "pr_opened", "comment", "review") and a.author.casefold() == cfg.me.casefold():
            seen.participated.add(a.number)
        seen.recent[a.id] = fmt_iso(a.ts)

    store = InboxStore(ws.inbox_path, ws.acks_path)
    added_ids = set()
    if entries:
        before = {e["id"] for e in store.entries()}
        store.append(entries)
        added_ids = {e["id"] for e in entries} - before
    result.new = [e for e in entries if e["id"] in added_ids]

    seen.cursors = new_cursor
    fsio.atomic_write_json(ws.seen_path, seen.to_json())
    for name, resp in probes.items():
        if not resp.not_modified and resp.etag:
            etags[urls[name]] = resp.etag
    fsio.atomic_write_json(ws.etags_path, etags)
    return result


def run_daemon(
    ws: Workspace,
    cfg: Config,
    gh,
    interval: int,
    on_round: Callable[[RoundResult], None],
    backfill: timedelta = timedelta(0),
    sleep: Callable[[float], None] = time.sleep,
    warn: Callable[[str], None] = lambda m: print(f"a2a: warning: {m}", file=sys.stderr),
    max_rounds: int | None = None,
) -> None:
    stop = {"flag": False}

    def handle(signum, frame):
        stop["flag"] = True
        raise KeyboardInterrupt

    previous = {s: signal.signal(s, handle) for s in (signal.SIGTERM,)}
    backoff = 0
    rounds = 0
    try:
        while not stop["flag"] and (max_rounds is None or rounds < max_rounds):
            rounds += 1
            try:
                result = run_round(ws, cfg, gh, backfill=backfill, warn=warn)
                backfill = timedelta(0)
                backoff = 0
                on_round(result)
                delay = max(interval, result.poll_interval or 0)
            except GhError as e:
                backoff = min(MAX_BACKOFF, max(interval, backoff * 2 or interval))
                warn(f"{e}; retrying in {backoff}s")
                delay = backoff
            if max_rounds is not None and rounds >= max_rounds:
                break
            sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        for s, h in previous.items():
            signal.signal(s, h)


def watch_lock(ws: Workspace) -> Any:
    return fsio.locked(ws.watch_lock_path, blocking=False)
