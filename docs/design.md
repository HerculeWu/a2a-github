# a2a-github — design

The agreed design, produced by grilling the [original spec](spec.md) on 2026-10-17. Terms follow [CONTEXT.md](../CONTEXT.md). Where this design departs from the spec, an ADR in [adr/](adr/) gives the reason. If this document and the spec disagree, this document wins.

## Layout

```
a2a/                 stdlib-only package (ADR-0003); knows nothing about Claude Code (ADR-0001)
  cli.py             argparse entry; global --json, --dir
  gh.py              GhClient, Response, GhError — the only place that spawns `gh` (ADR-0002)
  fake_gh.py         FakeGhClient, selected by A2A_GH_FAKE=1 (fixtures from A2A_GH_FAKE_DIR)
  workspace.py       Workspace discovery, config load + validation, `init` template
  fsio.py            atomic JSON write (tmp + fsync + os.replace), flock helpers, JSONL append
  timeutil.py        UTC parsing/formatting
  text.py            snippet, display-width truncation
  sign.py            Signature add / parse / strip, Author resolution
  activity.py        GitHub payload -> Activity normalization (pure)
  filters.py         Filter Rules + Exclusions (pure)
  watch.py           Watch Round orchestration
  inbox.py           Inbox store, acks, queries, line formatting
  fetch.py           Thread rendering + truncation (pure) and gh retrieval
  notify.py          Digest (pure) + Sinks
  state.py           State store
bin/a2a              plugin shim: puts the plugin root on sys.path, calls a2a.cli.main
skills/a2a/SKILL.md  agent-facing usage (English only)
.claude-plugin/      plugin.json + marketplace.json (source "./"; verify with `claude plugin validate`, else move plugin to plugin/)
pyproject.toml       console script `a2a = a2a.cli:main` for pip/pipx; dev extras pytest, pytest-cov
```

POSIX only (uses `fcntl`). All times are UTC: JSON uses `YYYY-MM-DDTHH:MM:SSZ`, and text lines use `YYYY-MM-DDTHH:MM`. `--since` takes ISO 8601; a naive value is read as UTC. Errors go to stderr as one line. Exit codes: 0 ok, 1 runtime error / not found, 2 usage error.

## Workspace

The Workspace is resolved in this order: `--dir`, then `A2A_DIR`, then the nearest `.a2a/` found walking up from cwd. `init` creates it in cwd, or in `--dir`/`A2A_DIR` when one is given.

| file | owner | content |
|---|---|---|
| `config.toml` | human | see below |
| `inbox.jsonl` | watch, append-only (ADR-0005) | one Inbox Entry per line |
| `acks.json` | inbox ack | `{"ids": [...]}` |
| `seen.json` | watch | per-stream cursors, ids near each cursor, Participated Threads, `initialized_at` (ADR-0006) |
| `etags.json` | watch | `{url: etag}` |
| `state.json` | consumer | flat JSON object |
| `notify.json` | notify | `{"last_announced": <entry id>}` |
| `.gitignore` | init | `*` |
| `*.lock` | — | flock files; `watch.lock` makes watch a singleton |

Every write is atomic (tmp file in the same directory, fsync, `os.replace`). Every read-modify-write holds an exclusive flock on `<file>.lock`.

### config.toml (what `init` writes)

```toml
repo = "org/repo"            # detected: gh repo view
login = "my-login"           # detected: gh api user
me = "my-login"              # = login for an own account; an agent name under a shared Login

[filters]
assignee = true
mentions = true
mention_aliases = []         # extra literal strings that address Me, e.g. ["agent-x:"]
participated = true
labels = ["pin:my-agent"]
title_regex = ""
body_regex = ""
ignore_self = true           # Exclusion: Author == Me
exclude_authors = []         # Exclusion: glob (* ?) on Author or Login, e.g. ["*[bot]"]

[watch]
interval = 60

[notify]
sink = "file"                # stdout | file | command
path = ".a2a/notify.log"     # file sink; relative to the Workspace's parent
# command = ["notify-send", "a2a"]   # command sink; a string is shlex-split; never run via a shell
```

`init [--repo R] [--me NAME] [--force]` falls back to placeholders when detection fails. When `me != login`:
- `init` warns if `gh api users/<me>` exists, because a mention would ping a real person (Q17);
- validation warns if `assignee = true` (ADR-0007).

`me` must match `[A-Za-z0-9._-]+`.

## Signatures and Authors (ADR-0007)

`a2a sign [--as NAME]` reads the body from stdin and writes it to stdout with `\n\n<sub>— NAME</sub>\n<!-- a2a:from=NAME -->` appended. If a Signature is already present it is replaced, never doubled. NAME defaults to `me`.

- **Author** is the name in the first `<!-- a2a:from=NAME -->` marker of the Activity's text, otherwise the Login (`user.login` / `actor.login`).
- Activities without text (assigned, labeled, closed, reopened, merged, review_requested) always use the Login.
- `fetch` shows Authors and strips Signatures from the text it prints.

## watch (ADR-0004, ADR-0006)

`a2a watch [--once] [--interval SEC] [--backfill DURATION] [--notify]`

### Streams

Fixed URLs. They never carry `since`, because a changing URL can never produce a 304.

| stream | URL (under `repos/{repo}/`) | yields |
|---|---|---|
| issues | `issues?state=all&sort=updated&direction=desc&per_page=100` | `issue_opened` / `pr_opened` (created after cursor); Thread snapshots; PRs to review-check |
| comments | `issues/comments?sort=updated&direction=desc&per_page=100` | `comment` (created after cursor; edits ignored) |
| review_comments | `pulls/comments?sort=updated&direction=desc&per_page=100` | no Activity of its own; marks its PR for review-check and supplies inline text |
| events | `issues/events?per_page=100` | `assigned`, `labeled`, `closed`, `reopened`, `merged`, `review_requested`; every other event type is ignored |
| reviews | `pulls/{n}/reviews` for flagged PRs only | `review` (submitted after cursor, state ≠ PENDING); its inline comments are folded in |

### One round

1. Probe each fixed URL with `If-None-Match`. Status comes from the `-i` status line, never from gh's exit code. ETags are compared ignoring the `W/` prefix.
2. **If every probe returns 304, stop.** No file is written, and `seen.json` is not read.
3. Otherwise:
   - follow `Link: next` (no ETag) until an item is older than the stream's cursor;
   - load `seen.json`;
   - normalize everything into Activities, sorted oldest first;
   - fetch `issues/{n}` for any Thread that has no snapshot.
4. For each Activity, in order:
   - resolve its Author;
   - run Exclusions, then Filter Rules;
   - then record participation: if the Author is Me (or Me opened the Thread), add the Thread to the Participated Threads.

   Participation is recorded after matching, so a reply in the same round that follows Me's comment does count as participated.
5. Append the matched Inbox Entries. Ids already in the Inbox are skipped, which makes a crash between steps 5 and 6 harmless.
6. Save `seen.json`, then `etags.json`.

### First run, Backfill and participation bootstrap

- **First run:** with no `seen.json`, cursors start at now minus `--backfill` (default 0), so history never floods the Inbox.
- **Participation bootstrap:** on the first run of an own-account Workspace (`me == login`), Participated Threads are seeded from three search API queries: `repo:R author:LOGIN`, `repo:R commenter:LOGIN` and `repo:R reviewed-by:LOGIN`. Under a shared Login they accumulate locally only.

### Daemon mode

- Sleeps for `max(interval, X-Poll-Interval)` between rounds.
- On a GhError it backs off exponentially, up to 15 min.
- Exits 0 on SIGINT/SIGTERM.
- Both daemon mode and `--once` hold `watch.lock`. A second watcher exits 1.
- `--notify` runs notify after any round that appended entries.

### Output

- Text: the number of new entries.
- `--json`: `{"new": [entries]}`.

## Filter Rules and Exclusions (pure: `filters.py`)

Inputs: the Activity, the Thread snapshot, the Participated Threads and the config. Output: a list of Matched Rules, or "excluded".

Exclusions are checked first and win over any match:
- `ignore_self`: Author == Me.
- `exclude_authors`: glob (only `*` and `?` are wildcards, so `*[bot]` works) against the Author or the Login.

Filter Rules (OR). An empty or false rule is disabled.

| rule | matches when | rule name in `matched_rules` |
|---|---|---|
| `assignee` | Me ∈ Thread assignees, or the Activity is `assigned`/`review_requested` targeting Me | `assignee` |
| `mentions` | `@me` with login-boundary regex `(?<![\w-])@ME(?![\w-])`, case-insensitive, in the Activity text; or any `mention_aliases` literal, case-insensitive | `mentions` |
| `labels` | the Thread carries the label, or the Activity is `labeled` with it | `labels:<label>`, one per label |
| `title_regex` | `re.search` on the Thread title | `title_regex` |
| `body_regex` | `re.search` on the Activity text | `body_regex` |
| `participated` | the Thread is in the Participated Threads before this Activity, or the Thread's Author is Me | `participated` |

## Inbox Entry

```json
{"id": "c-2384712", "ts": "2026-10-17T17:40:00Z", "type": "comment", "number": 123,
 "author": "agent-y", "login": "HerculeWu", "title": "Thread title",
 "snippet": "…", "url": "https://github.com/…", "matched_rules": ["mentions"]}
```

- **id prefixes:** `i-` issue/PR id (`*_opened`), `c-` comment id, `r-` review id, `e-` issue-event id.
- **`ts`:** when the Activity happened on GitHub.
- **`read`:** not stored; it is computed from `acks.json` on output (ADR-0005).
- **Snippet:** the text with its Signature stripped and whitespace collapsed to single spaces, at most 200 code points, ending in `…` when cut. Textless types get a synthetic snippet: `label: X`, `assignee: X`, `reviewer: X`, `closed`, `reopened`, `merged`. A review without a body uses its first inline comment, prefixed `path: `.

## inbox

- `a2a inbox list [--unread] [--since ISO] [--type T[,T]] [--limit N]`: entries in append order; `--limit` keeps the last N.
- `a2a inbox ack <id|#N>... | --all`: `#N` acks every entry of Thread N. Output: `acked K`; with `--json`, `{"acked": [ids]}`.
- `a2a inbox count [--unread]`: a single number; with `--json`, `{"count": n}`.

### Line format (golden-tested)

```
#123  comment   alice  2026-10-17T17:40  能不能改成…
```

Columns are separated by two spaces:
- the number column is padded to the widest number in the output;
- the type column is padded to `max(8, widest type)`;
- the author column is padded to the widest author;
- the time takes 16 characters;
- the snippet is cut to 60 display columns (East Asian Wide/Full characters count 2) and ends in `…`.

`--json` emits one JSON array of entries, each including `read`.

## fetch

`a2a fetch issue N [--since ISO] [--comments-only] [--max-chars N]` prints compact Markdown:

```
# #123 Title [open]
alice · 2026-10-17T17:40Z · labels: a, b · assignees: bob · https://github.com/…

<body>

## Comments (3 of 10 after 2026-10-16T00:00Z)
### alice · 2026-10-17T17:40Z
<text>
```

- `--since`: only comments created after that time.
- `--comments-only`: drops the body; the header stays.
- If N is a PR, the header says `[open · PR]`.
- `--max-chars` truncation (Q8):
  - the header is always kept;
  - the body is cut to a quarter of the budget, marked `[truncated]`;
  - comments are then added newest first while they fit, with `[truncated: K earlier comments omitted]` where the gap is;
  - if not even the newest comment fits, its head is kept, marked `[truncated]`.

`a2a fetch pr N [--since] [--comments-only] [--max-chars] [--files | --diff [PATH...]]`:
- **Default:**
  - the header adds `base ← head`, draft/merged state, and `+A −D in F files`;
  - the body;
  - then one merged timeline of comments and reviews. A review shows as `### bob · review APPROVED · ts`, followed by its body and its inline comments as `path:line: text`.
- **`--files`:** the header, then one line per file: `+12 −3  M  path`.
- **`--diff [PATH...]`:** the header, then the full patch from `gh pr diff N`, limited to the given paths, under `--max-chars` (head kept, `[truncated]`).

`--json` emits the structured Thread (`header`, `body`, `comments`/`timeline`, `files`, `diff`, `truncated`).

## notify

`a2a notify [--force] [--sink stdout|file|command]`

- With no unread entry after `last_announced`, it prints nothing and exits 0. `--force` sends whenever unread > 0.
- **Digest:** `inbox: 3 unread — #123 comment(alice), #130 assigned, #131 review(bob)`.
  - It lists the latest 5 unread entries in chronological order, then `, +K more`.
  - Text-bearing types show `(author)`; textless types do not.
- **Sinks:**
  - `stdout` prints the line.
  - `file` appends the line to `path`.
  - `command` runs argv with the Digest plus `\n` on stdin, with a 30 s timeout. A non-zero exit or a timeout makes notify exit 1.
- `notify.json` is updated only after a successful send.

## state

`a2a state get <key> | set <key> <value> [--raw] | delete <key> | dump`

- **`set`** parses the value as JSON and falls back to a plain string. `--raw` always stores a string.
- **`get`:**
  - in text mode it prints a string value raw and any other value as compact JSON;
  - a missing key prints nothing and exits 1.
- **`delete`** is idempotent and exits 0.
- **`dump`** prints `key=<json>` lines; with `--json`, the object.

Concurrent `set`s of different keys must both survive, which the flock guarantees.

## GhClient

```python
class GhClient:
    def __init__(self, run=subprocess.run, gh="gh"): ...
    def api(self, path, *, etag=None, method="GET", fields=None) -> Response   # `gh api -i`
    def run(self, *args) -> str                                                # e.g. ("pr", "diff", "5")
@dataclass
class Response: status: int; headers: dict; body: Any; etag: str | None; next_url: str | None
```

`make_gh()` returns `FakeGhClient(os.environ["A2A_GH_FAKE_DIR"])` when `A2A_GH_FAKE=1`. FakeGhClient:
- replays a fixture directory whose `routes.json` is `{path: {"etag", "body", "headers", "next"}}`;
- answers 304 when `If-None-Match` equals the route's ETag;
- records every call, so tests can assert on it.

## Tests

| layer | dir | content |
|---|---|---|
| a | `tests/unit/` | filters (each rule ±, OR combinations, Exclusions), snippet, sign/Author, fetch truncation and `--since`, golden inbox lines, digest |
| b | `tests/fake/` | `watch --once` on FakeGhClient + tmp Workspace; idempotence; all-304 round touches only `etags.json` (no writes, no `seen.json` read); fixture A then superset B adds only the difference; GhClient parsing with a mocked `run` |
| c | `tests/files/` | state round trip (nested, unicode), two-process concurrent set, ack then `--unread`, failure before `os.replace` leaves files intact |
| d | `tests/cli/` | `subprocess` runs of `a2a` with `A2A_GH_FAKE=1`; every `--json` output parses; the three notify Sinks |
| e | `tests/smoke/` | real repo, only when `A2A_TEST_REPO` is set |

Fixtures: `tmp_a2a_dir` and `fake_gh` in `tests/conftest.py`. Coverage target ≥ 85% (`pytest --cov=a2a`), with subprocess coverage enabled.

## Build order

Each primitive is one vertical slice and one commit: write its a/b tests (red), implement them (green), add its c/d tests, commit.

1. scaffold (GhClient, fsio, workspace, init)
2. state
3. inbox
4. sign
5. watch
6. fetch
7. notify
8. plugin + README (zh/en) + SKILL.md
9. smoke tests

## Deferred

- Inbox retention / prune.
- Edited text as Activity (ADR-0006).
- Grouping Activities from one Watch Round per Thread.
