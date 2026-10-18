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
    failed: list[str] = field(default_factory=list)


class Seen:
    """One repository's section of `seen.json`: per-stream cursors, ids near them, Participated Threads."""

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
            "initialized_at": self.initialized_at,
            "cursors": {k: fmt_iso(v) for k, v in sorted(self.cursors.items())},
            "recent": dict(sorted(recent.items())),
            "participated": sorted(self.participated),
        }


def load_sections(data: dict | None, repos: list[str], warn: Callable[[str], None]) -> dict[str, dict]:
    """`seen.json` sections keyed by casefolded repository; a flat 0.1 Seen is adopted or dropped."""
    if data is None:
        return {}
    if "repos" not in data:
        if len(repos) == 1:
            return {repos[0].casefold(): data}
        warn("seen.json predates repos and repos lists several repositories; starting a fresh baseline for each")
        return {}
    return {name.casefold(): section for name, section in data["repos"].items()}


def _etag_repo(url: str) -> str:
    parts = url.split("/")
    return "/".join(parts[1:3]).casefold() if parts[0] == "repos" and len(parts) > 3 else ""


@dataclass
class RepoPart:
    """One repository's share of a round, gathered before anything is written."""

    repo: str
    probes: dict[str, Any]
    seen: Seen
    first_run: bool
    cursors: dict[str, datetime]
    threads: dict[int, Thread]
    fresh: list[Activity]


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


def _bootstrap_participation(gh, repo: str, login: str) -> set[int]:
    numbers: set[int] = set()
    for qualifier in ("author", "commenter", "reviewed-by"):
        path = "search/issues?" + urlencode({"q": f"repo:{repo} {qualifier}:{login}", "per_page": 100})
        resp = gh.api(path)
        numbers.update(item["number"] for item in (resp.body or {}).get("items", []))
    return numbers


def _gather(gh, cfg: Config, repo: str, probes: dict, section: dict | None, now: datetime,
            backfill: timedelta, warn: Callable[[str], None]) -> RepoPart:
    """Page, normalize and snapshot one repository; raises GhError and writes nothing."""
    first_run = section is None
    seen = Seen.first_run(now - backfill, now) if first_run else Seen(section)

    items = {
        name: [] if resp.not_modified else _page_on(gh, resp, name, seen.floor(name)) for name, resp in probes.items()
    }

    threads: dict[int, Thread] = {}
    activities: list[tuple[Activity, str]] = []
    review_check: set[int] = set()
    inline_by_review: dict[int, list[dict]] = {}
    cursors = dict(seen.cursors)

    def advance(stream: str, ts: str) -> None:
        cursors[stream] = max(cursors[stream], parse_iso(ts))

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
        path = f"repos/{repo}/pulls/{number}/reviews?per_page=100"
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

    fresh = [a for a, stream in activities if seen.is_new(a, stream)]
    for a in fresh:
        if a.number not in threads:
            threads[a.number] = thread_from_issue(gh.api(f"repos/{repo}/issues/{a.number}").body)

    if first_run and cfg.filters.participated and not cfg.shared_login:
        try:
            seen.participated |= _bootstrap_participation(gh, repo, cfg.login)
        except GhError as e:
            warn(f"{repo}: could not bootstrap participated threads from search: {e}")

    return RepoPart(repo, probes, seen, first_run, cursors, threads, fresh)


def run_round(
    ws: Workspace,
    cfg: Config,
    gh,
    now: datetime | None = None,
    backfill: timedelta = timedelta(0),
    warn: Callable[[str], None] = lambda m: None,
) -> RoundResult:
    now = now or utc_now()
    etags: dict[str, str] = fsio.read_json(ws.etags_path, {})
    result = RoundResult()

    def fail(repo: str, e: GhError) -> None:
        warn(f"{repo} skipped this round: {e}")
        result.failed.append(repo)

    probed: dict[str, dict] = {}
    for repo in cfg.repos:
        urls = stream_urls(repo)
        try:
            probed[repo] = {name: gh.api(url, etag=etags.get(url)) for name, url in urls.items()}
        except GhError as e:
            fail(repo, e)
    intervals = [i for probes in probed.values() for i in (_poll_interval(r) for r in probes.values()) if i]
    result.poll_interval = max(intervals) if intervals else None
    # A repository whose probes all return 304 is done; when every one is, nothing is read or written.
    active = {repo: probes for repo, probes in probed.items() if not all(r.not_modified for r in probes.values())}
    if not active:
        return result

    sections = load_sections(fsio.read_json(ws.seen_path, None), cfg.repos, warn)
    parts: list[RepoPart] = []
    for repo, probes in active.items():
        try:
            parts.append(_gather(gh, cfg, repo, probes, sections.get(repo.casefold()), now, backfill, warn))
        except GhError as e:
            fail(repo, e)

    # The first round is a baseline: everything it sees already existed, so it only enters Seen.
    # An explicit Backfill is the one way to deliver part of it.
    def deliverable(a: Activity, part: RepoPart) -> bool:
        return not part.first_run or (backfill > timedelta(0) and a.ts >= now - backfill)

    merged = sorted(((a, part) for part in parts for a in part.fresh), key=lambda ap: ap[0].sort_key)
    entries = []
    for a, part in merged:
        thread = part.threads[a.number]
        decision = evaluate(a, thread, part.seen.participated, cfg)
        if decision.delivered and deliverable(a, part):
            entries.append(to_entry(a, thread, decision.matched, part.repo))
        if a.type in ("issue_opened", "pr_opened", "comment", "review") and a.author.casefold() == cfg.me.casefold():
            part.seen.participated.add(a.number)
        part.seen.recent[a.id] = fmt_iso(a.ts)

    store = InboxStore(ws.inbox_path, ws.acks_path)
    added_ids = set()
    if entries:
        before = {e["id"] for e in store.entries()}
        store.append(entries)
        added_ids = {e["id"] for e in entries} - before
    result.new = [e for e in entries if e["id"] in added_ids]

    # Repositories that were done or failed keep their section; dropped ones lose it.
    for part in parts:
        part.seen.cursors = part.cursors
        sections[part.repo.casefold()] = part.seen.to_json()
    saved = {repo: sections[repo.casefold()] for repo in cfg.repos if repo.casefold() in sections}
    fsio.atomic_write_json(ws.seen_path, {"repos": saved})
    # ETags are worth keeping only for repositories that have a Seen section.
    kept = {r.casefold() for r in saved}
    etags = {url: tag for url, tag in etags.items() if _etag_repo(url) in kept}
    for part in parts:
        urls = stream_urls(part.repo)
        for name, resp in part.probes.items():
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
            # Backfill only shapes a repository's first run, so it stays on for one whose first round failed.
            result = run_round(ws, cfg, gh, backfill=backfill, warn=warn)
            if len(result.failed) == len(cfg.repos):
                backoff = min(MAX_BACKOFF, max(interval, backoff * 2 or interval))
                warn(f"every repository failed; retrying in {backoff}s")
                delay = backoff
            else:
                backoff = 0
                on_round(result)
                delay = max(interval, result.poll_interval or 0)
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
