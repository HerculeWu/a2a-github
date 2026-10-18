"""Thread names `owner/name#N`: parse against `repos`, format (pure)."""

from __future__ import annotations

import re
from dataclasses import dataclass

THREAD_RE = re.compile(r"(?:(?P<repo>[A-Za-z0-9._-]+/[A-Za-z0-9._-]+)#|#)?(?P<number>[1-9][0-9]*)")


class ThreadNameError(ValueError):
    """A Thread name the user wrote in a form a2a does not accept: a usage error."""


@dataclass(frozen=True)
class ThreadRef:
    repo: str
    number: int
    bare: bool  # written as `#N` or `N`, so it stands for the one repository in `repos`


def parse_thread(token: str, repos: list[str]) -> ThreadRef:
    """Accept exactly `owner/name#N`, `#N` or `N`; a bare number needs exactly one repository."""
    m = THREAD_RE.fullmatch(token)
    if not m:
        raise ThreadNameError(f"not a thread: {token!r} — write owner/name#N")
    number = int(m.group("number"))
    repo = m.group("repo")
    if repo is None:
        if len(repos) != 1:
            raise ThreadNameError(f"ambiguous: #{number} — use owner/name#{number} (repos: {', '.join(repos)})")
        return ThreadRef(repos[0], number, bare=True)
    stored = next((r for r in repos if r.casefold() == repo.casefold()), repo)
    return ThreadRef(stored, number, bare=False)


def format_thread(repo: str | None, number: int) -> str:
    return f"{repo}#{number}" if repo else f"#{number}"
