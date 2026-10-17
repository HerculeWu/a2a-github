"""The only module that spawns `gh` (ADR-0002)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable

API_PREFIX = "https://api.github.com/"


class GhError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass
class Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    etag: str | None = None
    next_url: str | None = None

    @property
    def not_modified(self) -> bool:
        return self.status == 304


def etag_equal(a: str | None, b: str | None) -> bool:
    """GitHub may drop the weak `W/` prefix on a 304, so compare without it."""
    if not a or not b:
        return False
    return a.removeprefix("W/") == b.removeprefix("W/")


def next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        m = re.match(r'\s*<([^>]+)>\s*;\s*rel="next"', part)
        if m:
            return m.group(1).removeprefix(API_PREFIX)
    return None


def _parse_http(stdout: str) -> Response | None:
    m = re.match(r"HTTP/[\d.]+ (\d{3})[^\n]*\n", stdout)
    if not m:
        return None
    head, body_text = _split_head(stdout)
    headers: dict[str, str] = {}
    for line in head.splitlines()[1:]:
        name, sep, value = line.partition(":")
        if sep:
            headers[name.strip().lower()] = value.strip()
    body: Any = None
    if body_text.strip():
        try:
            body = json.loads(body_text)
        except json.JSONDecodeError:
            body = body_text
    return Response(
        status=int(m.group(1)),
        headers=headers,
        body=body,
        etag=headers.get("etag"),
        next_url=next_link(headers.get("link")),
    )


def _split_head(stdout: str) -> tuple[str, str]:
    parts = re.split(r"\r?\n\r?\n", stdout, maxsplit=1)
    return parts[0], parts[1] if len(parts) > 1 else ""


class GhClient:
    def __init__(self, run: Callable[..., subprocess.CompletedProcess] = subprocess.run, gh: str = "gh"):
        self._run = run
        self._gh = gh

    def _exec(self, argv: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
        try:
            return self._run(argv, capture_output=True, text=True, input=stdin)
        except FileNotFoundError as e:
            raise GhError(f"cannot run {self._gh!r}: {e}") from e

    def api(self, path: str, *, etag: str | None = None, method: str = "GET") -> Response:
        argv = [self._gh, "api", "-i"]
        if method != "GET":
            argv += ["-X", method]
        if etag:
            argv += ["-H", f"If-None-Match: {etag}"]
        argv.append(path.removeprefix(API_PREFIX))
        proc = self._exec(argv)
        resp = _parse_http(proc.stdout or "")
        if resp is None:
            msg = (proc.stderr or proc.stdout or "").strip() or f"gh exited {proc.returncode}"
            raise GhError(f"gh api {path}: {msg}")
        if resp.status == 304 or 200 <= resp.status < 300:
            return resp
        detail = resp.body.get("message") if isinstance(resp.body, dict) else (proc.stderr or "").strip()
        raise GhError(f"gh api {path}: HTTP {resp.status} {detail}".rstrip(), status=resp.status)

    def run(self, *args: str) -> str:
        proc = self._exec([self._gh, *args])
        if proc.returncode != 0:
            msg = (proc.stderr or "").strip() or f"exited {proc.returncode}"
            raise GhError(f"gh {' '.join(args)}: {msg}")
        return proc.stdout


def make_gh() -> Any:
    """Real client, or the fixture-replaying fake when A2A_GH_FAKE=1."""
    if os.environ.get("A2A_GH_FAKE") == "1":
        from a2a.fake_gh import FakeGhClient

        return FakeGhClient.from_dir(os.environ["A2A_GH_FAKE_DIR"])
    return GhClient()
