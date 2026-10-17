# Watch polls four resource endpoints with ETags, not the Events or Notifications APIs

A Watch Round probes four fixed URLs with `If-None-Match`: `issues?state=all&sort=updated&direction=desc&per_page=100`, `issues/comments?sort=updated&direction=desc&per_page=100`, `pulls/comments?sort=updated&direction=desc&per_page=100`, and `issues/events?per_page=100`. On a change it pages until it crosses its cursor, and fetches `pulls/{n}/reviews` only for PRs that changed. URLs never carry `since`, because a changing URL can never produce a 304. In steady state that is four requests per round, which cost nothing against the rate limit when they return 304.

## Considered Options

- **Repo Events API** (`/repos/{o}/{r}/events`): one feed, but the docs state 30s–6h latency, a 300-event / 30-day cap, and probes showed it out of order. Rejected.
- **Notifications API**: GitHub already computes mention/assign/participating reasons, but it is per Login across all repositories, so it cannot tell apart several Participants that share one Login. Its docs also list only classic PATs as supported tokens. Rejected.
- **Webhooks**: they need a publicly reachable receiver, which a local agent does not have. Rejected.
- **GraphQL**: it is served over POST, so it gets no ETag/304 support. Rejected.

## Consequences

There is no repo-wide reviews endpoint, and submitting a review does not reliably bump the PR's `updated_at` (observed 2026-10-17). New `pulls/comments` therefore also trigger a per-PR review check. `reviewed` is absent from `issues/events`. A 304 can return the ETag without its `W/` prefix, so ETags are compared ignoring it.
