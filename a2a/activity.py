"""Normalize GitHub REST payloads into Activities and Thread snapshots (pure)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from a2a.sign import author_of, strip_signature
from a2a.text import snippet
from a2a.timeutil import fmt_iso, parse_iso

TEXT_TYPES = frozenset({"issue_opened", "pr_opened", "comment", "review"})
EVENT_TYPES = frozenset({"assigned", "labeled", "closed", "reopened", "merged", "review_requested"})


@dataclass
class Thread:
    number: int
    title: str
    login: str
    body: str | None
    assignees: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    is_pr: bool = False
    url: str = ""

    @property
    def author(self) -> str:
        return author_of(self.body, self.login)


@dataclass
class Activity:
    id: str
    type: str
    ts: datetime
    number: int
    login: str
    text: str | None
    url: str
    target: str | None = None  # assignee, reviewer or label for textless types
    preview: str | None = None  # snippet source when it differs from `text`

    @property
    def author(self) -> str:
        return author_of(self.text, self.login) if self.type in TEXT_TYPES else self.login

    @property
    def sort_key(self) -> tuple[datetime, str]:
        return (self.ts, self.id)


def _login(obj) -> str:
    return (obj or {}).get("login") or "ghost"


def _number_from_url(url: str) -> int:
    m = re.search(r"/(?:issues|pulls)/(\d+)$", url or "")
    if not m:
        raise ValueError(f"no thread number in {url!r}")
    return int(m.group(1))


def thread_from_issue(item: dict) -> Thread:
    return Thread(
        number=item["number"],
        title=item.get("title") or "",
        login=_login(item.get("user")),
        body=item.get("body"),
        assignees=[_login(a) for a in item.get("assignees") or []],
        labels=[lb["name"] if isinstance(lb, dict) else str(lb) for lb in item.get("labels") or []],
        is_pr="pull_request" in item,
        url=item.get("html_url") or "",
    )


def opened_from_issue(item: dict) -> Activity:
    return Activity(
        id=f"i-{item['id']}",
        type="pr_opened" if "pull_request" in item else "issue_opened",
        ts=parse_iso(item["created_at"]),
        number=item["number"],
        login=_login(item.get("user")),
        text=item.get("body") or "",
        url=item.get("html_url") or "",
    )


def from_comment(item: dict) -> Activity:
    return Activity(
        id=f"c-{item['id']}",
        type="comment",
        ts=parse_iso(item["created_at"]),
        number=_number_from_url(item["issue_url"]),
        login=_login(item.get("user")),
        text=item.get("body") or "",
        url=item.get("html_url") or "",
    )


def from_event(item: dict) -> Activity | None:
    kind = item.get("event")
    if kind not in EVENT_TYPES:
        return None
    target = None
    if kind == "assigned":
        target = _login(item.get("assignee"))
    elif kind == "labeled":
        target = (item.get("label") or {}).get("name")
    elif kind == "review_requested":
        reviewer = item.get("requested_reviewer")
        team = item.get("requested_team")
        target = _login(reviewer) if reviewer else f"team:{(team or {}).get('slug') or (team or {}).get('name')}"
    issue = item.get("issue") or {}
    return Activity(
        id=f"e-{item['id']}",
        type=kind,
        ts=parse_iso(item["created_at"]),
        number=issue["number"],
        login=_login(item.get("actor")),
        text=None,
        url=issue.get("html_url") or "",
        target=target,
    )


def from_review(item: dict, number: int, inline: list[dict]) -> Activity | None:
    if item.get("state") == "PENDING" or not item.get("submitted_at"):
        return None
    body = item.get("body") or ""
    inline_texts = [c.get("body") or "" for c in inline]
    if body.strip():
        preview = body
    elif inline:
        preview = f"{inline[0].get('path')}: {inline[0].get('body') or ''}"
    else:
        preview = (item.get("state") or "commented").lower()
    return Activity(
        id=f"r-{item['id']}",
        type="review",
        ts=parse_iso(item["submitted_at"]),
        number=number,
        login=_login(item.get("user")),
        text="\n\n".join([body, *inline_texts]).strip(),
        url=item.get("html_url") or "",
        preview=preview,
    )


SYNTHETIC = {
    "assigned": "assignee: {}",
    "labeled": "label: {}",
    "review_requested": "reviewer: {}",
}


def entry_snippet(a: Activity) -> str:
    if a.type in TEXT_TYPES:
        return snippet(strip_signature(a.preview if a.preview is not None else a.text))
    if a.type in SYNTHETIC:
        return SYNTHETIC[a.type].format(a.target)
    return a.type


def to_entry(a: Activity, thread: Thread, matched_rules: list[str], repo: str) -> dict:
    return {
        "id": a.id,
        "ts": fmt_iso(a.ts),
        "type": a.type,
        "repo": repo,
        "number": a.number,
        "author": a.author,
        "login": a.login,
        "title": thread.title,
        "snippet": entry_snippet(a),
        "url": a.url,
        "matched_rules": matched_rules,
    }
