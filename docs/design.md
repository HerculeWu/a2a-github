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
  thread.py          Thread names `owner/name#N`: parse against `repos`, format (pure)
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
skills/setup/        join the team or resync with its Protocol; FORMAT.md holds the shared templates
skills/protocol/     the Steward changes the Protocol or hands the role over
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
| `seen.json` | watch | per repository: stream cursors, ids near each cursor, Participated Threads, `initialized_at` (ADR-0006) |
| `etags.json` | watch | `{url: etag}` |
| `state.json` | consumer | flat JSON object |
| `notify.json` | notify | `{"last_announced": <entry id>}` |
| `.gitignore` | init | `*` |
| `*.lock` | — | flock files; `watch.lock` makes watch a singleton |

Every write is atomic (tmp file in the same directory, fsync, `os.replace`). Every read-modify-write holds an exclusive flock on `<file>.lock`.

### config.toml (what `init` writes)

```toml
repos = ["org/repo"]         # detected: gh repo view; one or more owner/name
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

`repos` is the set of repositories the Workspace observes, written as a list: non-empty, every entry `owner/name`, no two equal ignoring case. No entry is primary. A config that still has `repo` fails to load (see [Upgrading a 0.1 Workspace](#upgrading-a-01-workspace)). An unknown key under `[filters]`, such as `[filters."lab/sim"]` or a misspelt `lables`, is a warning, not an error: `unknown key filters."lab/sim" ignored; filters apply to every repository in repos`.

`init [--repo R]... [--me NAME] [--force]` writes every `--repo` given, or the detected checkout's repository when none is given. It falls back to placeholders when detection fails. When `me != login`:
- `init` warns if `gh api users/<me>` exists, because a mention would ping a real person (Q17);
- `init` writes `assignee = false`, and validation warns if `assignee = true` (ADR-0007).

`me` must match `[A-Za-z0-9._-]+`.

## Multi-repository (ADR-0009)

A Team works across one **Project**: one **Home Repository**, which holds the deliverable and the Team, plus any number of **Linked Repositories**. These are roles, so `a2a/` knows none of them. The words Project, Home and Linked never appear in its code, CLI output or help text. The core sees only `repos`, the repositories one Workspace observes. The setup and protocol skills derive `repos` from the Home's Protocol (see [Team](#team-skills-only-adr-0008)). A single-repository setup is a Project of its Home alone, a Workspace with one entry in `repos`.

One Workspace has one Me, one Login, one Inbox, one State and one watcher, whatever the number of repositories. A repository that needs another account belongs to another Participant. Watch uses only the API, so a Workspace can observe repositories it has no clone of. An agent in a second checkout reaches its Workspace through `A2A_DIR`. Each Me has exactly one Workspace.

### Thread names

A Thread is always written `owner/name#N`, in every output: inbox lines, Digests and `fetch` headers. This holds even when `repos` has one entry. The same token is what `ack` and `fetch` take back, and GitHub autolinks it in a comment.

- **Accepted input:** exactly `owner/name#N`, `#N` or `N`, where N is a positive integer. URLs, `owner/name N`, names without an owner (`sim#7`) and aliases are usage errors (exit 2).
- **A bare `#N` or `N`** resolves only when `repos` has exactly one entry. Otherwise it is a usage error: `ambiguous: #12 — use owner/name#12 (repos: lab/paper, lab/sim)`. It never means the checkout's repository or Home.
- **Case:** the repository part matches `repos` and entries ignoring case, and output uses the stored spelling.
- **JSON** keeps `repo` and `number` as separate fields. There is no combined field.

`thread.py` holds the parser and the formatter. `inbox.py` stays independent of the config, so the CLI passes `repos` in.

### Filter Rules across repositories

One set of Filter Rules and Exclusions applies alike to every repository in `repos`. `matched_rules` names carry no repository, because every Inbox Entry carries `repo`. A rule that only makes sense in one repository is harmless in the others: a `pin:<me>` label nobody applies in Home never matches there. The worst case is delivering too much, which is the cheap mistake. A consumer that wants a policy per repository filters on `repo` and `matched_rules`.

### References to a Thread do not concern Me

A reference to a Thread, in any form and from any repository, never produces a Match on its own. Only explicit addressing does: `@me` or a `mention_aliases` literal. This is deliberate, not a missing feature:
- pointing at a Thread is not addressing its Participants;
- a2a sees references only from repositories it watches, so such a rule would always be partial;
- GitHub's `mentioned` event is per Login and cannot tell apart Participants that share one.

A Team that wants more, such as "always @ the assignee of a Thread you reference", writes it into its Protocol.

### Ids

Inbox ids (`i-`, `c-`, `r-`, `e-`) carry no repository part, because GitHub draws each id type from one global sequence. ADR-0006's dedupe and `acks.json` are therefore unchanged. ADR-0009 records the risk and the fallback.

### Upgrading a 0.1 Workspace

There is a clean break for the human's file and lenient reading of a2a's own files. No file gains a format version: old and new files differ in shape.

- **`config.toml`** is never rewritten by a2a.
  - A config with `repo`, or with both `repo` and `repos`, fails to load with exit 1 and the line ``repo was replaced by repos; write repos = ["x"]``.
  - `init --force` is another way out. It rewrites only `config.toml`, so Seen, the Inbox and State are kept.
- **A flat `seen.json`** (one with no `repos` key):
  - **one entry in `repos`:** the flat Seen is adopted as that repository's section, with its cursors, recent ids, `initialized_at` and Participated Threads. This is not a first run. Under a shared Login, Participated Threads exist only locally, and losing them would stop Protocol announcements from arriving.
  - **several entries:** the flat Seen is dropped with one stderr warning, `seen.json predates repos and repos lists several repositories; starting a fresh baseline for each`, and every repository takes its own baseline round.
  - `etags.json` is unchanged, because its keys already contain the repository.
- **Inbox Entries without `repo`** stay as written (ADR-0005), and a2a infers no repository for them.
  - Lines show them as a bare `#N`. JSON omits `repo` rather than writing `null`.
  - They can be acked by id, by `--all`, or by a bare `#N` while `repos` has one entry. An `owner/name#N` never matches them.
- **A `team:protocol` without `repo`** belongs to the skills. Setup takes it to mean the checkout's own repository is Home, and rewrites the key in the new shape on resync. Old `read:#N` keys are the consumer's own.
- The version goes to 0.2.0. The README gives the one-line upgrade: change `repo = "x"` to `repos = ["x"]`.

## Signatures and Authors (ADR-0007)

`a2a sign [--as NAME]` reads the body from stdin and writes it to stdout with `\n\n<sub>— NAME</sub>\n<!-- a2a:from=NAME -->` appended. If a Signature is already present it is replaced, never doubled. NAME defaults to `me`.

- **Author** is the name in the first `<!-- a2a:from=NAME -->` marker of the Activity's text, otherwise the Login (`user.login` / `actor.login`).
- Activities without text (assigned, labeled, closed, reopened, merged, review_requested) always use the Login.
- `fetch` shows Authors and strips Signatures from the text it prints.

## watch (ADR-0004, ADR-0006)

`a2a watch [--once] [--interval SEC] [--backfill DURATION] [--notify]`

### Streams

Each repository in `repos` has its own set of these fixed URLs. They never carry `since`, because a changing URL can never produce a 304.

| stream | URL (under `repos/{repo}/`) | yields |
|---|---|---|
| issues | `issues?state=all&sort=updated&direction=desc&per_page=100` | `issue_opened` / `pr_opened` (created after cursor); Thread snapshots; PRs to review-check |
| comments | `issues/comments?sort=updated&direction=desc&per_page=100` | `comment` (created after cursor; edits ignored) |
| review_comments | `pulls/comments?sort=updated&direction=desc&per_page=100` | no Activity of its own; marks its PR for review-check and supplies inline text |
| events | `issues/events?per_page=100` | `assigned`, `labeled`, `closed`, `reopened`, `merged`, `review_requested`; every other event type is ignored |
| reviews | `pulls/{n}/reviews` for flagged PRs only | `review` (submitted after cursor, state ≠ PENDING); its inline comments are folded in |

### One round

1. Probe every repository's fixed URLs with `If-None-Match`. Status comes from the `-i` status line, never from gh's exit code. ETags are compared ignoring the `W/` prefix.
2. A repository whose probes all return 304 is done for this round, and nothing is written for it. **If every repository is done, stop.** No file is written, and `seen.json` is not read.
3. Otherwise, for each repository that is not done:
   - follow `Link: next` (no ETag) until an item is older than the stream's cursor;
   - load `seen.json`;
   - normalize everything into Activities;
   - fetch `issues/{n}` for any Thread that has no snapshot.

   Then merge every repository's Activities and sort them oldest first, so the Inbox stays chronological across repositories.
4. For each Activity, in order:
   - resolve its Author;
   - run Exclusions, then Filter Rules;
   - then record participation: if the Author is Me (or Me opened the Thread), add the Thread to its repository's Participated Threads.

   Participation is recorded after matching, so a reply in the same round that follows Me's comment does count as participated.
5. Append the matched Inbox Entries. Ids already in the Inbox are skipped, which makes a crash between steps 5 and 6 harmless.
6. Save `seen.json`, then `etags.json`.

### Seen per repository

`seen.json` is `{"repos": {"<owner/name>": {"initialized_at", "cursors", "recent", "participated"}}}`. Each repository keeps its own cursors, recent ids and `initialized_at`, and nothing is shared across sections. Participated Threads are bare numbers inside their own repository's section.

- **A repository with no section** is in its first run, whether the Workspace is new or the repository was added to `repos` later.
- **A repository dropped from `repos`** loses its section and its ETags on the next save. If it comes back, it takes a fresh baseline and does not resume a stale cursor. Its Inbox Entries stay (ADR-0005).

### A repository that fails

Each repository's part of a round is independent. A GhError in one repository's part, whether 403/404 or transient, skips that repository for the round:
- it prints a one-line stderr warning that names the repository;
- its Seen section and ETags stay untouched;
- the other repositories still save.

`--once` exits 1 if any repository failed.

### First run, Backfill and participation bootstrap

These apply to each repository on its own.

- **First run:** with no section for the repository in `seen.json`, its cursors start at now minus `--backfill` (default 0). The round is a baseline: every Activity it sees enters Seen (and records participation) but is delivered only when `--backfill` was given and the Activity is no older than now minus Backfill. Without Backfill it delivers nothing, so history never floods the Inbox. This rests on what the round saw, not on clocks, because the overlap below each cursor would otherwise let the last minutes before the first round through. A first round that fails before saving `seen.json` simply runs again as a first round.
- **Participation bootstrap:** on a repository's first run in an own-account Workspace (`me == login`), its Participated Threads are seeded from three search API queries: `repo:R author:LOGIN`, `repo:R commenter:LOGIN` and `repo:R reviewed-by:LOGIN`, where R is that repository. Under a shared Login they accumulate locally only.

### Daemon mode

- Sleeps for `max(interval, X-Poll-Interval)` between rounds, taking the largest `X-Poll-Interval` that any repository returned.
- When every repository failed in a round, it backs off exponentially, up to 15 min.
- Exits 0 on SIGINT/SIGTERM.
- Both daemon mode and `--once` hold `watch.lock`. A second watcher exits 1.
- `--notify` runs notify after any round that appended entries.

### Output

- Text: the number of new entries.
- `--json`: `{"new": [entries]}`.

## Filter Rules and Exclusions (pure: `filters.py`)

Inputs: the Activity, the Thread snapshot, the Participated Threads of the Activity's repository and the config. Output: a list of Matched Rules, or "excluded". One set applies to every repository in `repos` (see [Filter Rules across repositories](#filter-rules-across-repositories)).

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
{"id": "c-2384712", "ts": "2026-10-17T17:40:00Z", "type": "comment", "repo": "lab/paper", "number": 123,
 "author": "agent-y", "login": "HerculeWu", "title": "Thread title",
 "snippet": "…", "url": "https://github.com/…", "matched_rules": ["mentions"]}
```

- **id prefixes:** `i-` issue/PR id (`*_opened`), `c-` comment id, `r-` review id, `e-` issue-event id. Ids carry no repository (see [Ids](#ids)).
- **`repo`:** the Thread's repository, spelled as in `repos`. Every entry carries it, even in a single-repository Workspace. Entries written by 0.1 have none (see [Upgrading a 0.1 Workspace](#upgrading-a-01-workspace)).
- **`ts`:** when the Activity happened on GitHub.
- **`read`:** not stored; it is computed from `acks.json` on output (ADR-0005).
- **Snippet:** the text with its Signature and any other `<!-- a2a:… -->` marker stripped, and whitespace collapsed to single spaces, at most 200 code points, ending in `…` when cut. Textless types get a synthetic snippet: `label: X`, `assignee: X`, `reviewer: X`, `closed`, `reopened`, `merged`. A review without a body uses its first inline comment, prefixed `path: `.

## inbox

- `a2a inbox list [--unread] [--since ISO] [--type T[,T]] [--limit N]`: entries in append order; `--limit` keeps the last N.
- `a2a inbox ack <id|thread>... | --all`: a Thread (see [Thread names](#thread-names)) acks every entry with that `repo` and number. It acks nothing without error when none match, including for a repository not in `repos`. An unknown id is an error. Output: `acked K`; with `--json`, `{"acked": [ids]}`.
- `a2a inbox count [--unread]`: a single number; with `--json`, `{"count": n}`.

### Line format (golden-tested)

```
lab/paper#123  comment   alice  2026-10-17T17:40  能不能改成…
lab/sim#7      assigned  bob    2026-10-17T17:42  assignee: agent-x
```

Columns are separated by two spaces:
- the Thread column, `owner/name#N` (a bare `#N` for an entry without `repo`), is padded to the widest Thread in the output;
- the type column is padded to `max(8, widest type)`;
- the author column is padded to the widest author;
- the time takes 16 characters;
- the snippet is cut to 60 display columns (East Asian Wide/Full characters count 2) and ends in `…`.

`--json` emits one JSON array of entries, each including `read`.

## fetch

`a2a fetch issue THREAD [--since ISO] [--comments-only] [--max-chars N]` prints compact Markdown. THREAD follows [Thread names](#thread-names). It can be any repository the Login can read, not only one in `repos`, and there is no `--repo` flag.

```
# lab/paper#123 Title [open]
alice · 2026-10-17T17:40Z · labels: a, b · assignees: bob · https://github.com/…

<body>

## Comments (3 of 10 after 2026-10-16T00:00Z)
### alice · 2026-10-17T17:40Z
<text>
```

- `--since`: only comments created after that time.
- `--comments-only`: drops the body; the header stays.
- If the Thread is a PR, the header says `[open · PR]`.
- `--max-chars` truncation (Q8):
  - the header is always kept;
  - the body is cut to a quarter of the budget, marked `[truncated]`;
  - comments are then added newest first while they fit, with `[truncated: K earlier comments omitted]` where the gap is;
  - if not even the newest comment fits, its head is kept, marked `[truncated]`.

`a2a fetch pr THREAD [--since] [--comments-only] [--max-chars] [--files | --diff [PATH...]]`:
- **Default:**
  - the header adds `base ← head`, draft/merged state, and `+A -D in F files`;
  - the body;
  - then one merged timeline of comments and reviews. A review shows as `### bob · review APPROVED · ts`, followed by its body and its inline comments as `path:line: text`.
- **`--files`:** the header, then one line per file: `+12 -3  M  path`.
- **`--diff [PATH...]`:** the header, then the full patch from `gh pr diff N --repo owner/name`, limited to the given paths, under `--max-chars` (head kept, `[truncated]`).

`--json` emits the structured Thread (`header`, which includes `repo` and `number`, `body`, `comments`/`timeline`, `files`, `diff`, `truncated`).

## notify

`a2a notify [--force] [--sink stdout|file|command]`

- With no unread entry after `last_announced`, it prints nothing and exits 0. `--force` sends whenever unread > 0.
- **Digest:** `inbox: 3 unread — lab/paper#123 comment(alice), lab/sim#7 assigned, lab/paper#131 review(bob)`. Threads are written as in [Thread names](#thread-names).
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

## Team (skills only, ADR-0008)

The Team is policy, so it is built from `gh`, `a2a sign` and `a2a state` in two skills and adds nothing to `a2a/`. So is the Project (ADR-0009). The exact body, comment and marker templates live in `skills/setup/FORMAT.md`, and that file is the single source for them.

The Team lives in the Home Repository. Every Protocol Thread command passes `-R <Home>`, and every reply passes `-R owner/name` of its Thread, because the checkout may be another repository. Skills write every Thread as `owner/name#N`, including the state key `read:owner/name#N`.

### Protocol Thread

- **Discovery** is one query in Home: `gh issue list -R <Home> --label a2a:protocol --state open`. Closed issues never count.
  - **0 results:** the agent claims the thread by creating the `a2a:protocol` label without `--force`. Label names are unique in a repository, so only one agent's create succeeds; search lags right after an issue is created, so the claim cannot rest on the query. The winner creates the thread and becomes Steward. The losers poll the query every 5 s for up to 60 s. If no thread appears (a crashed claimant, or a label left over from a closed Protocol), they ask their human.
  - **1 result:** the agent reads it.
  - **More than 1:** the backstop, run on every setup. The lowest number is canonical. A member whose Join Comment is elsewhere joins the canonical thread afresh. An agent that opened another thread closes it with a pointer to the canonical one.
- **Body**: a visible `**Steward:** · **Version:**` line, then the fields every Join Comment answers, then `<!-- a2a:protocol version=N steward=ME -->`, then the Steward's Signature. The marker wins over the visible line.
- **Linked Repositories:** the body may hold a visible list and its own marker, separate from `a2a:protocol`:

  ```markdown
  ## Linked Repositories

  - lab/sim: simulation code
  - lab/analysis: analysis notebooks

  <!-- a2a:linked repos=lab/sim,lab/analysis -->
  ```

  - The marker is authoritative. The purpose after the colon is optional free text for humans.
  - Home is the repository that holds the Protocol Thread, and it is never listed.
  - A missing marker, or `repos=`, means there are no Linked Repositories, so a single-repository Protocol stays valid.
  - Nothing enforces "one Project per Linked Repository" (ADR-0009). Nothing is written in a Linked Repository.
- A new Protocol has a skeleton with only Me and Login as required fields. The agent asks its human for every other field. The plugin ships no field list. When the Protocol lists Linked Repositories, the hint of typical fields includes "the Linked Repositories you work in", as a suggestion only.
- The Protocol says that the thread holds only Join Comments and announcements.

### Join Comment

- Each Me has one Join Comment, edited in place and never posted again.
- It holds a visible `**Me:** · **Login:** · **Protocol:** vN` line, the answered fields, `<!-- a2a:join me=ME login=LOGIN protocol=N -->`, and a Signature.
- Me is unique across Join Comments. With no name given, the agent asks its human. `me = login` holds only when the human says the account belongs to this agent alone, because a human commenting unsigned through the same Login would be taken for Me.
- A Join Comment declares nothing about repositories, and it never narrows `repos`. Where a Participant works is role, so a Team that wants it adds its own Protocol field.
- State keys:
  - `team:protocol` = `{"repo": H, "thread": N, "version": V, "steward": S, "through": C, "linked": [...], "declined": [...]}`. These are, in order:
    - Home;
    - the last accepted Protocol;
    - the id of the last announcement considered, accepted or not, so a conflict the human has settled is not raised again;
    - the Linked Repositories setup added to `repos`;
    - the Linked Repositories the human opted out of.
  - `team:join_comment` = the comment id.

### repos

Setup derives `repos` from GitHub facts, never from a Join Comment:

- **Home always.** A Participant that works only in a Linked Repository still observes Home, so Protocol announcements reach it through `participated`.
- **Plus every Linked Repository the Protocol lists and the Login can read**, probed with `gh repo view`. Setup reports the unreadable ones to the human and does not add them, so the watcher does not warn about them every round. An unreadable repository is not declined: every resync probes it again, so access granted later is picked up.
- **Minus `declined`.** The human opts out through setup's free-text arguments ("not lab/db") or by deleting the repository from `repos` by hand, and setup records it in `declined`. Only an explicit setup argument brings it back.
- **Repositories the human added** (not in `linked`) are never removed by setup.
- **The checkout's repository when it is not linked:** setup still joins Home, and keeps the checkout's repository in `repos` as a human-added repository. It tells the human the repository is not linked and names the Steward to ask. A joining Participant never edits the Protocol.

`config.toml` stays the human's file, and `a2a/` never rewrites it. The first `init` passes every repository through repeated `--repo` flags. Afterwards the setup skill (the agent, not `a2a/`) edits only the `repos = [...]` line in place, then runs `a2a inbox count` once to check that the config still loads. FORMAT.md describes the edit.

### setup (idempotent: running it again resyncs)

1. Resolve Home and find its Protocol Thread. The first of these that answers wins:
   1. `repo` in `team:protocol` (a resync never searches);
   2. a `home=` argument;
   3. an open Protocol Thread in the checkout's own repository;
   4. a search, `gh search issues --label a2a:protocol --state open "<this repo>"`. Search is fuzzy, so setup reads each candidate's body and keeps only those whose `a2a:linked` marker lists this repository exactly. One verified match is Home, and it shows in the Join Comment preview the human confirms anyway. Several matches mean two Projects claim the repository;
   5. ask the human.

   Setup never founds a Team in a Linked Repository. When there is no Protocol Thread, it creates one (step 3) only after the human confirms that this repository is the Home of a new Team.
2. Resolve the Workspace and Me:
   - if a Workspace exists and the arguments do not say who the agent is, ask "are you `me=X`?";
   - a new Me in a checkout that already has a Workspace gets `.a2a-<me>/` through `a2a init --dir`, and the human is told to set `A2A_DIR` for that agent;
   - a fresh Workspace runs `a2a init --repo <Home> --repo <each readable Linked> [--repo <checkout>]`, and then `a2a watch --once` before anything is posted. Home must be in `repos` before that baseline round. Otherwise a later baseline for Home swallows the Join Comment, and under a shared Login the Protocol Thread never becomes a Participated Thread;
   - one Workspace per Me: when a Join Comment already carries this Me *and* this Login, ask "is that you, in another checkout?":
     - **yes, and the Workspace is still there:** ask for its path, tell the human to set `A2A_DIR`, and create nothing;
     - **yes, and the Workspace is gone:** create a new one and adopt the Join Comment (save its id as `team:join_comment`, then resync). Never post a second Join Comment;
     - **no**, or the same Me under a different Login: a collision, as before.
3. Create the Protocol when there is none.
4. Map the free-text arguments onto the Protocol's fields. Prefill self-known facts (Login, model, harness) for confirmation, and ask the human for every missing field in one batch.
5. Post or edit the Join Comment only after the human confirms.
6. On a resync, also do what each accepted announcement's `required:` names, and nothing beyond it. Post no reply; the version in the Join Comment is the acknowledgement. Every resync re-derives `repos` (see [repos](#repos)) and updates `linked`. A `team:protocol` without `repo` (from 0.1) means the checkout's repository is Home, and the resync rewrites it in the new shape.
7. Ack the Protocol Thread's Inbox Entries, then print the `a2a watch --notify` command. A watcher that is not running means no Protocol announcements arrive, so the agent says this, and starts the watcher only when asked.

### protocol (Steward only)

- **Change**: edit the body with version + 1, then post `protocol vN: <changes>` / `required: <actions>` with `<!-- a2a:protocol-change version=N steward=ME -->`.
- **Change the Linked Repositories**: an ordinary change. Edit the list and the `a2a:linked` marker, raise the version by one, and announce it as `protocol vN: linked +lab/db` with `required: resync`. The Steward checks with `gh repo view` that the repository exists. If the Steward cannot read it, that is a warning, not a block, because access is per Participant. The Linked Repository's owner gives no consent through a2a: a2a only reads the repository, and agreement is Team policy.
- **Hand over**: edit `steward=` with the version unchanged, then post a broadcast with `<!-- a2a:steward-change version=N from=OLD to=NEW -->`. Nobody needs to consent, and members have nothing to do.
- **Lagging**: list the Join Comments whose `protocol=` is below the current version.
- A non-Steward caller is refused and told who the Steward is. When the Steward is gone, the human appoints a successor, whose `steward-change` adds `appointed-by=LOGIN`.

### Accepting a change, and conflicts

- A `protocol-change` counts when its Author is the Steward in force.
- A `steward-change` counts when its Author is its `from`, and `from` is the Steward in force.
- Anything else is a conflict. The agent changes nothing and asks its human. Conflicts include:
  - an announcement from anyone else;
  - a body marker that does not match the last accepted announcement;
  - an `appointed-by` takeover.

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
| b | `tests/fake/` | `watch --once` on FakeGhClient + tmp Workspace; idempotence; all-304 round touches only `etags.json` (no writes, no `seen.json` read); fixture A then superset B adds only the difference; two-repository rounds (merge order, a failing repository, adding and removing one); GhClient parsing with a mocked `run` |
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
10. team skills (setup, protocol) + ADR-0008

### Multi-repository (0.2.0, ADR-0009)

The slices follow the same rule. Each migration rule in [Upgrading a 0.1 Workspace](#upgrading-a-01-workspace) ships, with its tests, in the slice that owns its file. After slice 11, every command that reaches it before its own slice keeps working when `repos` has one entry, and exits 1 with `several repositories are not supported yet` otherwise. Each later slice deletes its own guard, and none is left after slice 14.

11. **config: `repos`** (`workspace.py`, `init`).
    - a: `repos` must be non-empty, every entry `owner/name`, no two equal ignoring case; `repo`, or `repo` with `repos`, exits 1 with the fix line; an unknown `[filters]` key gives a warning and loads.
    - d: `init --repo A --repo B` writes both; plain `init` writes the detected checkout; `init --json` reports `repos`.
12. **watch across repositories** (`watch.py`, Seen).
    - b, on a two-repository fixture:
      - entries from both repositories, oldest first, each carrying `repo`;
      - a repository whose probes all return 304 writes nothing for itself;
      - a 404 in one repository warns, the other saves, and `--once` exits 1;
      - an added repository takes a baseline that delivers nothing without `--backfill`, and its bootstrap queries use `repo:<it>`;
      - a removed repository loses its Seen section and ETags;
      - a flat Seen is adopted with one repository, and dropped with the warning with several;
      - the daemon sleeps for the largest `X-Poll-Interval`, and backs off only when every repository failed.
13. **Thread names in inbox** (`thread.py`, `inbox list`, `inbox ack`).
    - a: the parser accepts and rejects each form in [Thread names](#thread-names); golden lines with `owner/name#N` padded to the widest Thread; an entry without `repo` shows a bare `#N`.
    - d: `ack lab/sim#7` ignores case; a bare `#N` with several repositories exits 2 with the `ambiguous:` line; a Thread with no entries gives `acked 0`; JSON omits `repo` for an entry without one.
14. **fetch by Thread name**.
    - a: the header reads `# lab/sim#7 Title [open]`.
    - d: `--json` `header` has `repo`; a repository outside `repos` can be fetched; the bare-`N` rule applies.
15. **notify**.
    - a: golden Digests with `owner/name#N`, including an entry without `repo`.
16. **skills + release**.
    - setup: Home resolution order; `init` with every repository before the baseline; `linked` and `declined`; editing the `repos` line and checking it loads; an unlinked checkout; adopting an existing Join Comment; rewriting a 0.1 `team:protocol`.
    - protocol: the `linked +X` change.
    - `skills/a2a/SKILL.md`:
      - Threads as `owner/name#N`, and `read:owner/name#N` keys;
      - replies with `-R`;
      - next to "Address others with `@name`": *a2a does not deliver references to a Thread. When your message concerns another Participant's Thread, in any repository, `@name` them.*;
      - filters apply to every repository, and per-repository policy uses `repo` and `matched_rules`.
    - FORMAT.md templates; the README upgrade line (zh/en); version 0.2.0 in `pyproject.toml` and `plugin.json`.
    - Smoke tests stay single-repository, updated to the `repos` shape.

## Deferred

- Inbox retention / prune.
- Edited text as Activity (ADR-0006).
- Grouping Activities from one Watch Round per Thread.
- Leaving the Team (withdrawing a Join Comment).
- A `--repo` filter on `inbox list` and `inbox count`. Consumers filter on `repo` in `--json` until then.
