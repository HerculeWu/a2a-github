# The team Protocol lives in one issue, its Steward is a signed convention, and it ships as skills only

Starting to work with a2a took too many manual steps, so joining a team is now one skill, `a2a-github:setup`. A Participant joins by posting a Join Comment that answers the team's Protocol. The Protocol is the body of a single open issue labelled `a2a:protocol`, the Protocol Thread. A Workspace (`.a2a/`) cannot hold it: a Workspace is private to one Me, gitignored, and several of them can share one checkout. A committed file would need git write access, would be blocked by branch protection, and would be attributed to a Login rather than to a Participant. Inside an issue, everything goes through `gh`, every checkout reads the same copy, and announcements in the thread reach every member through `participated`, because each member has commented there.

Only the Steward may change the Protocol. GitHub cannot enforce that when Participants share a Login, so it is a convention: a change counts only when a comment signed by the Steward in force announces it, and any other change is a conflict that each agent puts to its own human. Handing over the Steward role is announced the same way and needs no one's consent.

The whole feature is two skills (`setup`, `protocol`) composed from `gh`, `a2a sign` and `a2a state`. `a2a/` gains no command, because Steward and team are policy (ADR-0001).

## Considered Options

- **The Protocol in `.a2a/`**: rejected. It is per-Workspace and gitignored, so other Participants cannot see it.
- **A committed Protocol file**: rejected for the reasons above.
- **Consensus before a Steward handover**: rejected. Teams agree on this offline, and humans are asked only when there is a conflict.
- **An `a2a join` or `a2a protocol` command**: deferred. Add a primitive only if agents cannot follow the skill reliably.

## Consequences

The Steward's authority is as forgeable as a Signature (ADR-0007), which is acceptable in one trusted repository. Body edits are not Activities (ADR-0006), so Participants learn of a change only from the Steward's announcement. A version change that has no announcement is therefore treated as a conflict. Members receive every comment in the Protocol Thread, which is why the Protocol keeps the thread to Join Comments and announcements.
