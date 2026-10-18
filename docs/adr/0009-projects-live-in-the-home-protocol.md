# A Project's repositories are listed only in its Home's Protocol, and a2a only observes several repositories

A Team now works across several repositories: one Home Repository, which holds the deliverable and the Team, and any number of Linked Repositories. Project, Home and Linked are roles, so they stay out of `a2a/` (ADR-0001), as the Team does (ADR-0008). The core gains one role-free feature, a Workspace that observes the repositories listed in `repos`. It never learns which of them is Home. The skills hold everything else, built from `gh`, `a2a sign` and `a2a state`.

The Project's makeup is stored once, in the Home Repository's Protocol body, as an `a2a:linked` marker that only the Steward changes. Nothing is written in any Linked Repository. Every Participant can read Home, but a Linked Repository may belong to another owner and be readable by only some Participants. The atomic claims GitHub offers on the Linked side (creating a label, or a repository variable through a raw POST) both need Write there. A variable is also invisible to anyone without collaborator access. So the link points one way: Home names its Linked Repositories, and a Linked Repository does not know its Home. Setup finds Home from a Linked checkout by an argument, then by a search that it verifies against the marker, then by asking the human. Each Workspace's `repos` is derived from the marker on setup and refreshed on resync.

## Considered Options

- **A label or repository variable in each Linked Repository pointing at Home**: rejected. It needs Write on a repository the Team may not own, and a variable cannot be read by most Participants.
- **Topics or custom properties**: rejected. A topic cannot hold `owner/name`, and custom properties exist only for organizations.
- **An `a2a project`, `a2a link` or `a2a home` command**: deferred, as ADR-0008 deferred `a2a join`. Add a primitive only if agents cannot follow the skill reliably.
- **One Workspace per repository, or an aggregator over several Workspaces**: rejected. A Participant has one Me, one Login and one Inbox, and a single watcher keeps the Inbox in chronological order across repositories.
- **A Home flag in `config.toml`**: rejected. Nothing in the core would use it, and it would put a role into the core.

## Consequences

- Nothing stops a Linked Repository being listed by two Projects. Setup treats more than one verified search match as a question for the human, and otherwise the assumption goes unchecked.
- A Participant who works only in a Linked Repository still observes Home. That is how Protocol announcements reach it, through `participated`.
- Inbox ids keep no repository part (`c-2384712`), so ADR-0006's dedupe and `acks.json` are unchanged. This relies on GitHub drawing each id type from one global sequence, which GitHub does not document. If two repositories ever produce the same id, the fix is to prefix ids with the repository and accept that every Workspace re-delivers once.
- Thread numbers are per repository, so every Thread is written `owner/name#N`, and a bare `#N` is accepted only while `repos` has a single entry.
