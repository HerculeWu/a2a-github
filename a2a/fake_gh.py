"""Fixture-replaying stand-in for GhClient, selected by A2A_GH_FAKE=1.

A fixture directory holds `routes.json` ({path: {"etag", "body", "headers", "next", "status"}})
and optionally `commands.json` ({"pr diff 5": "stdout"}).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from a2a.gh import API_PREFIX, GhError, Response, etag_equal


class FakeGhClient:
    def __init__(self, routes: dict[str, Any], commands: dict[str, str] | None = None):
        self.routes = routes
        self.commands = commands or {}
        self.calls: list[dict[str, Any]] = []

    @classmethod
    def from_dir(cls, directory: str | Path) -> "FakeGhClient":
        d = Path(directory)
        routes = json.loads((d / "routes.json").read_text(encoding="utf-8"))
        cmd_file = d / "commands.json"
        commands = json.loads(cmd_file.read_text(encoding="utf-8")) if cmd_file.exists() else {}
        return cls(routes, commands)

    def api(self, path: str, *, etag: str | None = None, method: str = "GET") -> Response:
        path = path.removeprefix(API_PREFIX)
        self.calls.append({"kind": "api", "path": path, "etag": etag, "method": method})
        route = self.routes.get(path)
        if route is None:
            raise GhError(f"gh api {path}: HTTP 404 Not Found", status=404)
        status = route.get("status", 200)
        if status >= 400:
            raise GhError(f"gh api {path}: HTTP {status}", status=status)
        route_etag = route.get("etag")
        if etag and etag_equal(etag, route_etag):
            return Response(status=304, etag=route_etag)
        headers = {k.lower(): str(v) for k, v in route.get("headers", {}).items()}
        return Response(status=status, headers=headers, body=route.get("body"), etag=route_etag, next_url=route.get("next"))

    def run(self, *args: str) -> str:
        key = " ".join(args)
        self.calls.append({"kind": "run", "args": list(args)})
        if key not in self.commands:
            raise GhError(f"gh {key}: no fake output recorded")
        return self.commands[key]
