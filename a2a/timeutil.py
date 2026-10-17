"""All a2a times are UTC."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_iso(text: str) -> datetime:
    """ISO 8601 date or datetime; a value without an offset is read as UTC."""
    try:
        dt = datetime.fromisoformat(text.strip())
    except (ValueError, AttributeError) as e:
        raise ValueError(f"not an ISO 8601 time: {text!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fmt_short(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")


_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(text: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([smhdw]?)", text.strip())
    if not m:
        raise ValueError(f"not a duration (e.g. 90s, 15m, 2h, 7d): {text!r}")
    return timedelta(seconds=int(m.group(1)) * _UNITS[m.group(2) or "s"])
