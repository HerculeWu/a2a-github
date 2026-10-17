# Standard library only at runtime

The `a2a` package depends on nothing but the Python 3.11+ standard library (`tomllib` for config) and the external `gh` binary. This lets it run anywhere an agent has Python, including inside a Claude Code plugin with no install step. Consequences: no HTTP client, no TOML writer (the `init` template is emitted as literal text), and file locking uses `fcntl`, which ties concurrent-safety guarantees to POSIX. Test-only tools (pytest, pytest-cov) are dev dependencies and are exempt.
