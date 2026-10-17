"""Crash-safe local file primitives: atomic replace, flock, JSONL append."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


@contextlib.contextmanager
def locked(path: Path, blocking: bool = True) -> Iterator[None]:
    """Exclusive advisory lock on `<path>.lock`; guards read-modify-write of `path`."""
    lock_path = Path(f"{path}.lock")
    with open(lock_path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def append_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        return
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    with locked(path), open(path, "a", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(path: Path) -> list[dict]:
    """All complete records; a torn final line from an interrupted append is ignored."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
