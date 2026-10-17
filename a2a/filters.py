"""Filter Rules and Exclusions (pure). Rules combine with OR; Exclusions win."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from a2a.activity import Activity, Thread
from a2a.workspace import Config


@dataclass
class Decision:
    matched: list[str] = field(default_factory=list)
    excluded: str | None = None

    @property
    def delivered(self) -> bool:
        return self.excluded is None and bool(self.matched)


def _same(a: str | None, b: str | None) -> bool:
    return a is not None and b is not None and a.casefold() == b.casefold()


def glob_match(pattern: str, value: str) -> bool:
    """Case-insensitive glob with only `*` and `?`, so `*[bot]` matches `dependabot[bot]`."""
    regex = "".join(".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern)
    return re.fullmatch(regex, value, re.IGNORECASE | re.DOTALL) is not None


def mentions(text: str, cfg: Config) -> bool:
    if re.search(rf"(?<![\w-])@{re.escape(cfg.me)}(?![\w-])", text, re.IGNORECASE):
        return True
    folded = text.casefold()
    return any(alias and alias.casefold() in folded for alias in cfg.filters.mention_aliases)


def evaluate(a: Activity, thread: Thread, participated: set[int], cfg: Config) -> Decision:
    f = cfg.filters
    author = a.author
    if f.ignore_self and _same(author, cfg.me):
        return Decision(excluded="ignore_self")
    for pattern in f.exclude_authors:
        if glob_match(pattern, author) or glob_match(pattern, a.login):
            return Decision(excluded="exclude_authors")

    text = a.text or ""
    rules: list[str] = []
    if f.assignee and (
        any(_same(x, cfg.me) for x in thread.assignees)
        or (a.type in ("assigned", "review_requested") and _same(a.target, cfg.me))
    ):
        rules.append("assignee")
    if f.mentions and text and mentions(text, cfg):
        rules.append("mentions")
    for label in f.labels:
        on_thread = any(_same(x, label) for x in thread.labels)
        if on_thread or (a.type == "labeled" and _same(a.target, label)):
            rules.append(f"labels:{label}")
    if f.title_regex and re.search(f.title_regex, thread.title):
        rules.append("title_regex")
    if f.body_regex and text and re.search(f.body_regex, text):
        rules.append("body_regex")
    if f.participated and (thread.number in participated or _same(thread.author, cfg.me)):
        rules.append("participated")
    return Decision(matched=rules)
