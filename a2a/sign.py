"""Signatures tell apart Participants that share one Login (ADR-0007)."""

from __future__ import annotations

import re

from a2a.workspace import NAME_RE

MARKER_RE = re.compile(r"<!--\s*a2a:from=([A-Za-z0-9._-]+)\s*-->")
# The visible line `sign` writes, the hidden marker, and the blank lines before them.
SIGNATURE_RE = re.compile(r"\s*(?:<sub>— [A-Za-z0-9._-]+</sub>\s*)?<!--\s*a2a:from=[A-Za-z0-9._-]+\s*-->\s*")


def signature(name: str) -> str:
    return f"<sub>— {name}</sub>\n<!-- a2a:from={name} -->"


def strip_signature(text: str | None) -> str:
    return SIGNATURE_RE.sub(" ", text or "").strip() if MARKER_RE.search(text or "") else (text or "").strip()


def sign(body: str, name: str) -> str:
    if not NAME_RE.match(name):
        raise ValueError(f"signature name must match {NAME_RE.pattern}, got {name!r}")
    text = strip_signature(body)
    return f"{text}\n\n{signature(name)}" if text else signature(name)


def signed_by(text: str | None) -> str | None:
    m = MARKER_RE.search(text or "")
    return m.group(1) if m else None


def author_of(text: str | None, login: str) -> str:
    """The Participant an Activity is attributed to: its Signature, else its Login."""
    return signed_by(text) or login
