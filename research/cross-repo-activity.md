# How GitHub's REST API surfaces Activity across repositories

Research for [#3](https://github.com/HerculeWu/a2a-github/issues/3), map [#1](https://github.com/HerculeWu/a2a-github/issues/1). Checked 2026-10-18 against docs.github.com and with `gh api` against public repositories (`cli/cli`, `rails/rails`, `microsoft/vscode`), authenticated with gh's OAuth token (`gho_…`, scopes `repo read:org gist workflow`).

Terms follow [CONTEXT.md](../CONTEXT.md). "Streams" are the four fixed URLs plus per-PR reviews from [design.md](../docs/design.md) "watch" and [ADR-0004](../docs/adr/0004-poll-resource-endpoints-with-etags.md).

## 1. Are the ids a2a dedupes on unique across GitHub?

**Answer: yes, in practice, within each object type. They are not unique across types, and they are addressed only through their repository.**

- The REST reference types every one of them as `integer, format: int64`, with no stated scope ([issue comments](https://docs.github.com/en/rest/issues/comments), [reviews](https://docs.github.com/en/rest/pulls/reviews), [issue events](https://docs.github.com/en/rest/issues/events)). No page states "unique across GitHub" in words.
- Observed: ids come from one global sequence per type, interleaved across repositories in creation order. Newest issue comments:

  | repo | comment id | created_at |
  |---|---|---|
  | cli/cli | 6248384404 | 2026-10-18T09:44:46Z |
  | rails/rails | 6249114559 | 2026-10-18T11:07:05Z |
  | rails/rails | 6249529687 | 2026-10-18T11:46:14Z |
  | microsoft/vscode | 6249874713 | 2026-10-18T12:23:52Z |
  | microsoft/vscode | 6249975498 | 2026-10-18T12:34:44Z |

  Issue ids (~5.91e9), review ids (~5.56e9), review-comment ids (~4.31e9) and issue-event ids (~3.36e10) show the same pattern.
- The new-format `node_id` is base64url msgpack `[0, repository_id, database_id]`. `IC_kwDODKw3uc8AAAABdG7HlA` decodes to `[0, 212613049, 6248384404]`, where 212613049 is `cli/cli`'s repository id. The REST `id` is the database id. The node id carries the repository, but the database id does not depend on it.
- Ids are resolved only under their repository: `GET repos/cli/cli/issues/comments/6249529687` returns 404, while the same id under `rails/rails` resolves.
- Type ranges overlap (issue ids ~5.9e9 have passed review ids ~5.56e9), so a bare number is not unique across types. a2a's `i-`/`c-`/`r-`/`e-` prefixes already handle this.

**For a2a:** ADR-0006's keys stay collision-free when several repositories feed one Inbox, given the type prefix. Anything that turns an id back into a request (fetch, a snapshot) must keep the repository with the id. Thread numbers, unlike ids, are per repository: `#12` exists in every repository.

## 2. Cross-repository references and @mentions

Case: a comment or body in repository X contains `owner/Y#12` (or a URL to it), or `@login`.

| what | where it shows | in a2a's streams? |
|---|---|---|
| The text itself | X's `issues/comments`, X's issue/PR body, `pulls/comments`, review bodies | Yes, **only if X is watched** |
| `cross-referenced` on Y#12 | Y's **timeline only**: [issue event types](https://docs.github.com/en/rest/using-the-rest-api/issue-event-types#cross-referenced) list it "Not supported" for the issue events API, "Supported" for the timeline | **No** |
| Bump of Y#12's `updated_at` | none observed | **No** |
| `referenced` (a commit message names the issue; `commit_repository` may differ) | issue events and timeline | Yes, Y's `issues/events` (a2a ignores the type today) |
| `connected` (manual link between issues/PRs) | issue events and timeline | Yes, Y's `issues/events` (ignored today) |
| `mentioned` (the `actor` is the mentioned user) | issue events and timeline, in the repository **where the text is** | Yes, but per Login, so it cannot tell apart Participants that share a Login |

Evidence:

- `cli/cli#14727` gained a `cross-referenced` timeline item from `devblac/prw#19` at 2026-10-18T06:11:55Z, but its `updated_at` stayed 2026-10-17T15:26:56Z. A cross-reference does not move the target into the `issues?sort=updated` stream.
- On the first page of `cli/cli`'s `issues/events?per_page=100` the types were `added_to_project_v2, closed, labeled, project_v2_item_status_changed, referenced, reopened, subscribed, unlabeled, unsubscribed`. There was no `cross-referenced`.
- **`cross-referenced` timeline items have no `id` and no `node_id`.** Seven items on five `cli/cli` threads all lacked both. ADR-0006 cannot key them. A key would have to be synthesized, e.g. `(source issue id, target repo, target number)`, since `source.issue` carries the referencing issue's full object and repository.
- [Timeline](https://docs.github.com/en/rest/issues/timeline) is per Thread (`GET /repos/{o}/{r}/issues/{n}/timeline`, `per_page` ≤ 100, no `since`). It does return an ETag and answers 304 (verified on `cli/cli#14727`).

**Cost to see them:**

- **Free** (no extra requests) for a reference whose source is a watched repository. The referencing text is already in X's streams, so a2a can parse `owner/repo#N`, `repo#N`, and `https://github.com/owner/repo/(issues|pull)/N` out of the Activity text it already has.
- **Per Thread** for references from unwatched repositories. Since nothing bumps the target, a2a cannot tell which Thread to look at. It would have to probe the timeline of every Thread it cares about, every round: one request per Thread, free when 304 (§3). The calls are 304s, but probes grow with Participated Threads × repositories.

A mention follows the same rule. It is only ever visible in the repository whose text contains it: `@me` in repository X reaches Me only if some Workspace watches X.

## 3. Conditional requests and the rate limit

- Docs: "Making a conditional request does not count against your primary rate limit if a `304` response is returned and the request was made while correctly authorized with an `Authorization` header" ([best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)). The same page says to "use the same parameters every time you poll", which matches ADR-0004's fixed URLs.
- Verified: one 200 on `repos/cli/cli/issues/comments?…&per_page=1`, then three 304s with `If-None-Match`. `X-RateLimit-Used` stayed 12, and `GET /rate_limit` agreed. The same held on a timeline URL (used 74 → 74). The 304 echoed the ETag without `W/`, as ADR-0004 notes.
- Primary limit is 5,000/h **per user**, shared by every token and app acting as that Login ([rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)). During this probe, `X-RateLimit-Used` rose 12 → 70 in a few minutes from other sessions using the same Login. Every Workspace and every other tool under one Login draws on one budget.
- Secondary limits: ≤ 100 concurrent requests, ≤ 900 points/min for REST (a GET is 1 point), and 90 s of CPU per 60 s ([same page](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)). The docs do not say whether a 304 costs secondary-limit points. Treat that as unknown.

## 4. Request cost per Watch Round for N repositories

With the current design run once per repository:

- **Steady state:** 4·N probes, all 304. Zero primary cost, but 4·N HTTP round trips. At `interval = 60`, that is 240·N requests/h of latency and secondary-limit exposure, and nothing against the 5,000.
- **A stream that changed:** 1 (the 200) + follow-up pages until the cursor is crossed, usually 0. Then +1 `pulls/{n}/reviews` per flagged PR, and +1 `issues/{n}` per Thread without a snapshot. All of these count.
- **First run:** the participation bootstrap adds 3 search queries per repository (`author:`, `commenter:`, `reviewed-by:`). These draw on the separate search budget of 30 requests/min ([search](https://docs.github.com/en/rest/search/search)). N ≥ 10 repositories in one first round reaches that limit.
- **P Workspaces** (Participants on one machine or one Login) each poll on their own, so the totals multiply by P. Only the 200s count, and they are shared per Login.
- **Upper bound** if every probe returned 200 every minute: 240·N·P/h. That exhausts 5,000/h at N·P ≈ 20. Real cost is proportional to how many streams change, not to N.

## 5. Endpoints that cover several repositories at once

| endpoint | covers | 304 | usable under a shared Login? |
|---|---|---|---|
| [Notifications](https://docs.github.com/en/rest/activity/notifications) `GET /notifications`, also per repo `GET /repos/{o}/{r}/notifications` | threads the Login is subscribed to, with `reason` (`mention`, `assign`, `review_requested`, `author`, `comment`, `subscribed`, …) | yes (`Last-Modified`/`If-Modified-Since`; `X-Poll-Interval: 60` observed) | **No.** Reasons are per Login, so Participants sharing it are indistinguishable, and GitHub does not normally notify a user of their own actions (not stated in the REST reference and not verified here), which would hide everything a shared-Login team does. The docs say only classic PATs work, but gh's OAuth token (`gho_`, scope `repo`) returned 200 here, so ADR-0004's token concern is weaker than stated. |
| [Events](https://docs.github.com/en/rest/activity/events) `GET /orgs/{org}/events`, `/users/{u}/received_events`, `/users/{u}/events/orgs/{org}`, `/networks/{o}/{r}/events` | one org, or repositories the user watches / people followed | yes (ETag) | Technically yes, but "latency can be anywhere from 30s to 6h", "up to 300 events", "past 30 days". An org feed does not cover a cross-owner Project. Rejected for the same reasons as the repo events feed in ADR-0004. |
| [Search issues](https://docs.github.com/en/rest/search/search) `q=repo:A repo:B …` | issues/PRs in any listed repositories (several `repo:` qualifiers are OR'd; observed: one query returned both repositories' results, 69,740 total) | **no ETag returned; every call counts** (verified: 29 → 28 remaining) | Yes, with Login-only qualifiers (`involves:`, `mentions:`), so it has the same per-Login blind spot. 30 req/min, 1,000-result cap, ≤ 5 boolean operators, 256-char query. It reports Threads by `updated_at` only (no comments/events), so cross-references are still invisible. |
| GraphQL | anything, many repositories per query | no (POST) | Rejected in ADR-0004 (no 304, point-based cost on every poll). |

**Conclusion:** there is no multi-repository endpoint that beats 4·N free 304 probes for a shared Login. Per-repository streams remain the right primitive. Batching would only save round trips, not rate limit.

## Implications for the open design questions on #1

- **Workspace model:** ids are safe to merge into one Inbox. **Thread numbers are not**: `inbox ack #N`, the Inbox Entry's `number`, Participated Threads, Thread snapshots, `fetch issue N`, and `etags.json`/cursor keys all need the repository once there is more than one. Cursors and ETags are per URL and so already per repository.
- **Cross-repository references as relevance:** a2a can only see a reference from inside a watched repository, by parsing text it already has, at no extra cost. A reference arriving in Home from an unwatched repository leaves no trace in any polled stream. It also has no id to dedupe on, and seeing it would mean per-Thread timeline probes. With Linked Repositories that every relevant Participant watches, text parsing covers the Project.
- **Filter Rules:** `mentions` already works on text, so it carries over per repository unchanged. GitHub's own `mentioned` events and the notifications reasons stay unusable under a shared Login.
