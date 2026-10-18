# a2a-github

A role-agnostic capability layer that lets humans and agents collaborate through GitHub repositories. It tells a participant what new activity concerns them, cheaply, without pulling full issue threads into an agent's context. It decides nothing about who should handle what.

## Language

### Participants

**Participant**:
A human or an agent that reads and writes issues and PRs in the shared repository.
_Avoid_: User, actor, member

**Login**:
The GitHub account that a Workspace's `gh` authentication acts as. Several Participants may share one Login, e.g. one human running many agents under their own account.
_Avoid_: Account, user, token

**Me**:
The Participant a given Workspace acts for, named by `me` in its config. Equals the Login when the Participant has its own GitHub account; otherwise a distinct name under a shared Login. Every filter decision is relative to Me.
_Avoid_: Self, owner, current user

**Workspace**:
One `.a2a/` directory: one Me acting through one Login, one Inbox, one State, observing one or more repositories.
_Avoid_: Profile, home, data dir

**Signature**:
A hidden marker appended to text a Participant posts, naming which Participant wrote it. It lets Participants that share one Login tell each other apart.
_Avoid_: Tag, stamp, header

**Author**:
The Participant an Activity is attributed to: the name in its Signature if it has one, otherwise its Login. Activities that carry no text, such as labeling or assigning, are always attributed to the Login.
_Avoid_: Actor, sender, poster

### Project

**Project**:
The repositories whose work serves one deliverable, carried by one Team: exactly one Home Repository and any number of Linked Repositories. A single-repository setup is a Project of its Home alone.
_Avoid_: Workspace (that is one `.a2a/`), organization, monorepo

**Home Repository**:
The repository that holds a Project's deliverable, such as the paper of a research project. The Team lives there, and every Participant can read it.
_Avoid_: Main repo, hub, primary, root

**Linked Repository**:
A repository whose work feeds the Project's deliverable, such as simulation, analysis or database operations. It belongs to one Project at a time. A Participant may be able to read only some Linked Repositories.
_Avoid_: Satellite, child repo, secondary repo

### Team

**Team**:
The Participants that have a Join Comment in the Protocol Thread.
_Avoid_: Group, org, crew

**Protocol**:
The team's own agreement about what a Participant declares when it joins, such as its capabilities, permissions, model or harness. The team decides its content; a2a requires only that it names a Steward and carries a version.
_Avoid_: Rules, charter, policy

**Protocol Thread**:
The single issue in the Home Repository whose body is the Protocol. The team joins and is told about Protocol changes in its comments.
_Avoid_: Roster issue, team issue

**Steward**:
The one Participant allowed to change the Protocol. The Participant that created it is the Steward until the Steward hands the role to someone else.
_Avoid_: Owner, admin, maintainer

**Join Comment**:
A Participant's one comment in the Protocol Thread that declares who it is (its Me and Login) and whatever else the Protocol asks, answered against a stated Protocol version. It is edited in place when the Protocol changes, never posted again.
_Avoid_: Registration, roster entry, profile

### Observing the repository

**Activity**:
A single thing that happened in the repository — an issue opened, a comment posted, a label added, a review submitted — normalized into one shape regardless of which GitHub endpoint reported it. Editing existing text is not an Activity.
_Avoid_: Event (ambiguous with GitHub's Events API and issue events), update, change

**Activity Type**:
The kind of an Activity: `issue_opened`, `pr_opened`, `comment`, `review`, `assigned`, `labeled`, `closed`, `reopened`, `merged`, `review_requested`. A review and its inline comments form one `review` Activity.
_Avoid_: Kind, category

**Thread**:
An issue or a PR together with its comments and reviews, identified by its repository and number and written `owner/name#N`. Issues and PRs in one repository share one number space.
_Avoid_: Conversation, ticket

**Watch Round**:
One pass of the watcher over every repository a Workspace observes that turns new Activities into Inbox Entries.
_Avoid_: Poll, tick, cycle, sync

**Seen**:
The record of Activities already considered, so that a repeated or restarted Watch Round never produces the same Inbox Entry twice.
_Avoid_: Cache, history

**Backfill**:
Deliberately extending a Workspace's first Watch Round into the past. Without it, a Workspace observes only Activity that happens after its first Watch Round.
_Avoid_: Import, history sync

### Deciding relevance

**Filter Rule**:
One configured criterion (`assignee`, `mentions`, `labels`, `title_regex`, `body_regex`, `participated`) that judges whether an Activity concerns Me. Rules combine with OR. `assignee`, `labels` and `participated` judge the Thread's current state, so they match any Activity in a qualifying Thread, not only the moment it began to qualify.
_Avoid_: Policy, route, subscription

**Exclusion**:
A configured criterion (`ignore_self`, `exclude_authors`) that keeps an Activity out of the Inbox even when it Matches. Exclusions always win over Filter Rules.
_Avoid_: Block, mute, deny rule

**Match**:
The outcome of an Activity satisfying at least one Filter Rule; carries the list of Matched Rules.
_Avoid_: Hit, trigger

**Matched Rules**:
The names of every Filter Rule an Activity satisfied, recorded so the consumer can apply its own policy.
_Avoid_: Reasons, tags

**Participated Thread**:
A Thread that Me authored, commented in, or reviewed, so later Activity in it concerns Me.
_Avoid_: Involved, subscribed, watched

### Consuming

**Inbox**:
The ordered collection of Inbox Entries for one Workspace.
_Avoid_: Feed, queue, notifications

**Inbox Entry**:
A matched Activity as stored for consumption: who, what, where, a Snippet, its Matched Rules, and whether it is Read.
_Avoid_: Notification, message, item

**Snippet**:
A single-line preview of an Activity's text, bounded in length, meant to let a reader decide whether to Fetch.
_Avoid_: Summary, excerpt, preview

**Read**:
The state of an Inbox Entry that a consumer has acknowledged. Acknowledging is called **Ack**.
_Avoid_: Seen (that term belongs to the watcher), done, handled

**Fetch**:
Retrieving one Thread on demand, in compact form, optionally narrowed by time or size.
_Avoid_: Load, sync, pull

**Notify**:
Pushing a one-line Digest of unread Inbox Entries to a Sink.
_Avoid_: Alert, ping

**Digest**:
The one-line text that Notify sends, e.g. `inbox: 3 unread — lab/paper#123 comment(alice), lab/sim#130 assigned`. Notify sends a Digest only when there are unread Inbox Entries it has not already announced.
_Avoid_: Summary, report

**Sink**:
A configured destination for a Digest: stdout, a file, or a command that reads it on stdin.
_Avoid_: Channel, transport, target

**State**:
A flat key–value store owned by the Workspace's consumer, for whatever bookkeeping its own policy needs. a2a never interprets it.
_Avoid_: Memory, cache, config

## Relationships

- A **Workspace** belongs to exactly one **Me** and one **Login**, and observes one or more repositories through that Login. Each **Me** has exactly one Workspace, however many checkouts it works in.
- A **Watch Round** turns **Activities** into **Inbox Entries** when they produce a **Match**; every considered Activity enters **Seen** whether or not it matched.
- An **Inbox Entry** refers to one **Thread** by repository and number; a Thread can have many Inbox Entries.
- An Activity becomes an **Inbox Entry** only if it Matches and no **Exclusion** applies; by default Activity whose **Author** is **Me** is excluded.
- A **Workspace** has one set of **Filter Rules** and **Exclusions**, applied alike to every repository it observes.
- **Seen** belongs to the watcher; **Read** belongs to the consumer. They are independent.
- **Notify** reads the **Inbox**, never the repository.
- A **Project** has one **Team**, and its only open **Protocol Thread** is in its **Home Repository**; each **Participant** in the team has exactly one **Join Comment** in it.
- A **Project**'s **Linked Repositories** are listed in its **Protocol**; only the **Steward** changes that list.
- A **Protocol** change counts only when the **Steward** of the previous version announces it in the Protocol Thread.
