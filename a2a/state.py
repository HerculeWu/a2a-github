"""State: a flat JSON key-value store owned by the consumer; a2a never interprets it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from a2a import fsio


def parse_value(text: str, raw: bool = False) -> Any:
    """JSON if it parses, else the literal string; `raw` always keeps the string."""
    if raw:
        return text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def format_value(value: Any) -> str:
    return value if isinstance(value, str) else compact(value)


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _read(self) -> dict[str, Any]:
        data = fsio.read_json(self.path, {})
        if not isinstance(data, dict):
            raise ValueError(f"{self.path} is not a JSON object")
        return data

    def get(self, key: str) -> Any:
        return self._read()[key]

    def dump(self) -> dict[str, Any]:
        return self._read()

    def set(self, key: str, value: Any) -> None:
        with fsio.locked(self.path):
            data = self._read()
            data[key] = value
            fsio.atomic_write_json(self.path, data)

    def delete(self, key: str) -> bool:
        with fsio.locked(self.path):
            data = self._read()
            if key not in data:
                return False
            del data[key]
            fsio.atomic_write_json(self.path, data)
            return True
