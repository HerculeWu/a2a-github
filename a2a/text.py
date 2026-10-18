from __future__ import annotations

import re
import unicodedata

SNIPPET_LEN = 200

# Hidden markers such as `<!-- a2a:join … -->` are for machines, not for a one-line preview.
A2A_MARKER_RE = re.compile(r"<!--\s*a2a:[^>]*-->")


def snippet(text: str | None, limit: int = SNIPPET_LEN) -> str:
    """Single line, a2a markers dropped, whitespace collapsed, at most `limit` code points ending in `…` when cut."""
    flat = " ".join(A2A_MARKER_RE.sub(" ", text or "").split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1] + "…"


def char_width(ch: str) -> int:
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def display_width(text: str) -> int:
    return sum(char_width(c) for c in text)


def truncate_display(text: str, width: int) -> str:
    """Cut to at most `width` terminal columns, ending in `…` when cut."""
    if display_width(text) <= width:
        return text
    out, used = [], 0
    for ch in text:
        w = char_width(ch)
        if used + w > width - 1:
            break
        out.append(ch)
        used += w
    return "".join(out) + "…"
