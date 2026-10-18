"""Fetch one Thread on demand, rendered as compact Markdown that fits a character budget."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from a2a.sign import author_of, strip_signature
from a2a.thread import format_thread
from a2a.timeutil import fmt_iso, fmt_short, parse_iso

TRUNC = " [truncated]"
FILE_STATUS = {"added": "A", "removed": "D", "modified": "M", "renamed": "R", "copied": "C", "changed": "M"}


def _when(dt: datetime) -> str:
    return fmt_short(dt) + "Z"


@dataclass
class Post:
    author: str
    login: str
    ts: datetime
    text: str
    kind: str = "comment"
    state: str | None = None
    inline: list[str] = field(default_factory=list)

    def render(self) -> str:
        head = f"### {self.author} · review {self.state} · {_when(self.ts)}" if self.kind == "review" else f"### {self.author} · {_when(self.ts)}"
        parts = [head]
        if self.text:
            parts.append(self.text)
        parts.extend(f"- {line}" for line in self.inline)
        return "\n".join(parts)

    def to_json(self) -> dict:
        data = {"author": self.author, "login": self.login, "ts": fmt_iso(self.ts), "text": self.text}
        if self.kind == "review":
            data.update(kind="review", state=self.state, inline=self.inline)
        return data


@dataclass
class ThreadView:
    header: str
    body: str | None
    posts: list[Post]
    total: int
    since: datetime | None = None
    section: str = "Comments"


@dataclass
class Rendered:
    text: str
    body: str | None
    posts: list[Post]
    omitted: int = 0
    truncated: bool = False
    data: dict = field(default_factory=dict)


def after(posts: list[Post], since: datetime | None) -> list[Post]:
    return posts if since is None else [p for p in posts if p.ts > since]


def _render(view: ThreadView, body: str | None, posts: list[Post], omitted: int) -> str:
    parts = [view.header]
    if body:
        parts.append(body)
    if view.total:
        count = f"{len(view.posts)} of {view.total} after {_when(view.since)}" if view.since else str(view.total)
        section = f"## {view.section} ({count})"
        if omitted:
            noun = "comments" if view.section == "Comments" else "entries"
            section += f"\n[truncated: {omitted} earlier {noun} omitted]"
        parts.append(section + ("\n" + "\n\n".join(p.render() for p in posts) if posts else ""))
    return "\n\n".join(parts)


def fit(view: ThreadView, max_chars: int | None) -> Rendered:
    """Keep the header, a quarter of the budget for the body, then the newest posts that fit."""
    full = _render(view, view.body, view.posts, 0)
    if max_chars is None or len(full) <= max_chars:
        return Rendered(full, view.body, view.posts)
    body = view.body
    quarter = max_chars // 4
    if body and len(body) > quarter:
        body = body[:quarter].rstrip() + TRUNC
    chosen: list[Post] = []
    for post in reversed(view.posts):
        trial = [post, *chosen]
        if len(_render(view, body, trial, len(view.posts) - len(trial))) > max_chars:
            break
        chosen = trial
    if not chosen and view.posts:
        newest = view.posts[-1]
        omitted = len(view.posts) - 1
        room = max_chars - len(_render(view, body, [replace(newest, text="", inline=[])], omitted)) - len(TRUNC) - 1
        if room > 0:
            chosen = [replace(newest, text=newest.text[:room].rstrip() + TRUNC, inline=[])]
    omitted = len(view.posts) - len(chosen)
    text = _render(view, body, chosen, omitted)
    if len(text) > max_chars and body:
        room = max_chars - len(_render(view, None, chosen, omitted)) - len(TRUNC) - 2
        body = body[:room].rstrip() + TRUNC if room > 0 else None
        text = _render(view, body, chosen, omitted)
    if len(text) > max_chars:
        text = text[: max(0, max_chars - len(TRUNC))].rstrip() + TRUNC
    return Rendered(text, body, chosen, omitted, truncated=True)


def _get_all(gh, path: str) -> list[dict]:
    resp = gh.api(path)
    items = list(resp.body or [])
    while resp.next_url:
        resp = gh.api(resp.next_url)
        items.extend(resp.body or [])
    return items


def _names(items, key: str) -> list[str]:
    return [i[key] if isinstance(i, dict) else str(i) for i in items or []]


def _comment_post(c: dict) -> Post:
    login = (c.get("user") or {}).get("login") or "ghost"
    return Post(author=author_of(c.get("body"), login), login=login, ts=parse_iso(c["created_at"]), text=strip_signature(c.get("body")))


def _header(repo: str, item: dict, state: str, extra: list[str]) -> str:
    login = (item.get("user") or {}).get("login") or "ghost"
    meta = [author_of(item.get("body"), login), _when(parse_iso(item["created_at"])), *extra]
    labels = _names(item.get("labels"), "name")
    assignees = _names(item.get("assignees"), "login")
    if labels:
        meta.append("labels: " + ", ".join(labels))
    if assignees:
        meta.append("assignees: " + ", ".join(assignees))
    meta.append(item.get("html_url") or "")
    return f"# {format_thread(repo, item['number'])} {item.get('title') or ''} [{state}]\n" + " · ".join(meta)


def _thread_json(repo: str, item: dict, rendered: Rendered, view: ThreadView, is_pr: bool) -> dict:
    login = (item.get("user") or {}).get("login") or "ghost"
    return {
        "repo": repo,
        "number": item["number"],
        "title": item.get("title"),
        "state": item.get("state"),
        "is_pr": is_pr,
        "author": author_of(item.get("body"), login),
        "login": login,
        "created_at": item.get("created_at"),
        "url": item.get("html_url"),
        "labels": _names(item.get("labels"), "name"),
        "assignees": _names(item.get("assignees"), "login"),
        "body": rendered.body,
        "total_comments": view.total,
        "omitted": rendered.omitted,
        "truncated": rendered.truncated,
    }


def fetch_issue(gh, repo: str, number: int, since: datetime | None = None, comments_only: bool = False,
                max_chars: int | None = None) -> Rendered:
    item = gh.api(f"repos/{repo}/issues/{number}").body
    is_pr = "pull_request" in item
    state = item.get("state", "open") + (" · PR" if is_pr else "")
    posts = [_comment_post(c) for c in _get_all(gh, f"repos/{repo}/issues/{number}/comments?per_page=100")]
    body = None if comments_only else strip_signature(item.get("body"))
    view = ThreadView(_header(repo, item, state, []), body, after(posts, since), len(posts), since)
    out = fit(view, max_chars)
    out.data = {**_thread_json(repo, item, out, view, is_pr), "comments": [p.to_json() for p in out.posts]}
    return out


def _pr_head(repo: str, pr: dict) -> str:
    state = "merged" if pr.get("merged") else pr.get("state", "open")
    state += " · PR" + (" · draft" if pr.get("draft") else "")
    extra = [
        f"{pr['base']['ref']} ← {pr['head']['ref']}",
        f"+{pr.get('additions', 0)} -{pr.get('deletions', 0)} in {pr.get('changed_files', 0)} files",
    ]
    return _header(repo, pr, state, extra)


def _split_diff(diff: str, paths: list[str]) -> str:
    if not paths:
        return diff
    keep, sections, current = [], [], []
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git ") and current:
            sections.append(current)
            current = []
        current.append(line)
    if current:
        sections.append(current)
    for sec in sections:
        names = sec[0].strip().split(" ")[2:4]
        names = [n[2:] if n[:2] in ("a/", "b/") else n for n in names]
        if any(n == p or n.startswith(p.rstrip("/") + "/") for n in names for p in paths):
            keep.extend(sec)
    return "".join(keep)


def fetch_pr(gh, repo: str, number: int, since: datetime | None = None, comments_only: bool = False,
             max_chars: int | None = None, files: bool = False, diff: bool = False,
             paths: list[str] | None = None) -> Rendered:
    pr = gh.api(f"repos/{repo}/pulls/{number}").body
    header = _pr_head(repo, pr)

    if files:
        listing = _get_all(gh, f"repos/{repo}/pulls/{number}/files?per_page=100")
        rows = [
            {"path": f["filename"], "status": f.get("status"), "additions": f.get("additions", 0), "deletions": f.get("deletions", 0)}
            for f in listing
        ]
        lines = [f"+{r['additions']} -{r['deletions']}  {FILE_STATUS.get(r['status'], '?')}  {r['path']}" for r in rows]
        text = header + "\n\n" + "\n".join(lines)
        return Rendered(text, None, [], data={"repo": repo, "number": number, "header": header, "files": rows, "truncated": False})

    if diff:
        patch = _split_diff(gh.run("pr", "diff", str(number), "--repo", repo), paths or [])
        text = f"{header}\n\n```diff\n{patch.rstrip()}\n```"
        truncated = max_chars is not None and len(text) > max_chars
        if truncated:
            text = text[: max_chars - len(TRUNC) - 1].rstrip() + "\n" + TRUNC.strip()
        return Rendered(text, None, [], truncated=truncated,
                        data={"repo": repo, "number": number, "header": header, "diff": patch, "truncated": truncated})

    comments = [_comment_post(c) for c in _get_all(gh, f"repos/{repo}/issues/{number}/comments?per_page=100")]
    inline: dict[Any, list[dict]] = {}
    for c in _get_all(gh, f"repos/{repo}/pulls/{number}/comments?per_page=100"):
        inline.setdefault(c.get("pull_request_review_id"), []).append(c)
    reviews = []
    for r in _get_all(gh, f"repos/{repo}/pulls/{number}/reviews?per_page=100"):
        if r.get("state") == "PENDING" or not r.get("submitted_at"):
            continue
        login = (r.get("user") or {}).get("login") or "ghost"
        notes = [
            f"{c.get('path')}:{c.get('line') or c.get('original_line') or '?'}: {' '.join(strip_signature(c.get('body')).split())}"
            for c in sorted(inline.get(r["id"], []), key=lambda c: c["created_at"])
        ]
        reviews.append(Post(author=author_of(r.get("body"), login), login=login, ts=parse_iso(r["submitted_at"]),
                            text=strip_signature(r.get("body")), kind="review", state=r.get("state"), inline=notes))
    timeline = sorted(comments + reviews, key=lambda p: p.ts)
    body = None if comments_only else strip_signature(pr.get("body"))
    view = ThreadView(header, body, after(timeline, since), len(timeline), since, section="Timeline")
    out = fit(view, max_chars)
    out.data = {
        **_thread_json(repo, pr, out, view, True),
        "state": "merged" if pr.get("merged") else pr.get("state"),
        "draft": bool(pr.get("draft")),
        "base": pr["base"]["ref"],
        "head": pr["head"]["ref"],
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "changed_files": pr.get("changed_files"),
        "timeline": [p.to_json() for p in out.posts],
    }
    return out
