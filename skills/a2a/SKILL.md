---
name: a2a
description: Collaborate through a shared GitHub repository with the `a2a` CLI. Use when checking what is new for you in the repo (inbox, notifications, assignments, mentions), when reading one issue or PR without flooding context, when replying on GitHub as one of several agents sharing a login, or when setting up or running the repo watcher.
---

# a2a: GitHub collaboration primitives

`a2a` turns repository activity into a small **inbox** of entries that concern you, and lets you read just the **thread** you need. It decides nothing about who handles what. That policy is yours, or it comes from your instructions.

Every command accepts `--json` for machine-readable output. Use `--json` whenever you will parse the result. The default text is terse and meant to be read.

## The loop

1. **Check cheaply:** run `a2a inbox count --unread`. It prints one number. At `0`, stop here.
2. **Triage:** run `a2a inbox list --unread`. You get one line per entry: `#N  type  author  time  snippet`. The snippet is often enough to decide that an entry needs no action.
3. **Read only the thread you will act on**, as narrowly as possible:
   - `a2a fetch issue N --since <time of the last thing you read> --max-chars 4000`
   - For a PR: `a2a fetch pr N` (conversation and reviews), `--files` (changed files), `--diff path/…` (only the patches you need).
   - `--comments-only` drops the opening post you have already read.
4. **Act**, for example by replying. When you post anything, **sign** it: `printf '%s' "$BODY" | a2a sign | gh issue comment N -F -`. The same pipe works for `gh pr comment`, `gh pr review` and `gh issue create`. The signature is how other participants, and your own watcher, tell you apart from everyone else using the same GitHub account.
5. **Acknowledge** what you handled: `a2a inbox ack #N` acks every entry of thread N; `a2a inbox ack <id>` acks a single entry.

## Keeping context small

- Fetch only after the inbox tells you something changed. Fetch only that thread, never the whole repository.
- Remember where you stopped reading: `a2a state set "read:#N" "<ISO time>"`. Next time, use `a2a state get "read:#N"` as the `--since` value.
- Fit output to a budget with `--max-chars`. The header and the newest comments are kept, and older comments are reported as omitted.
- Use `a2a inbox list --unread --type review,assigned` (or `--limit N`) to narrow triage.

## State

`a2a state get|set|delete|dump` is a flat JSON key-value store for your own bookkeeping: cursors, claimed threads, notes to your future self. `set` stores JSON when the value parses as JSON, and a string otherwise. `--raw` forces a string. `get` exits 1 when the key is missing.

## The watcher

Entries only appear after the watcher runs:
- `a2a watch --once` runs one polling round and prints how many entries it added.
- A long-running `a2a watch [--notify]` usually runs outside your session (in a terminal, a service, or cron). Start it only when asked.
- `a2a notify` sends a one-line digest of new unread entries to the configured sink, at most once per new arrival. `--sink stdout` prints the digest instead.

## Setup and identity

- "no a2a workspace found" means there is no `.a2a/` directory yet. Run `a2a init` in the repository root, or `a2a init --me <agent-name>` when you share a GitHub login with others. Then review `.a2a/config.toml`.
- `me` is who you are. When it differs from `login`, several participants share that account, and you are identified by your signature. Address others with `@name`. Inbox `author` values already resolve signatures to participant names.
- Several agents in one checkout each use their own workspace: `A2A_DIR=/path/to/agent-x-workspace a2a …`.
- Filter rules (which activity counts as yours) live in `config.toml` under `[filters]`. The `matched_rules` field of each entry says why it matched.
