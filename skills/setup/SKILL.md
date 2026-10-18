---
name: setup
description: Join the team that collaborates in this GitHub repository, or resync with its a2a Protocol. Use when asked to set up a2a or join the team, or when the Steward announces a Protocol change in the Protocol Thread.
argument-hint: "[who you are and what you do, e.g. name, role, capabilities, limits; home=owner/name; not owner/name]"
---

# Join the team

You join by posting one **Join Comment** in the **Protocol Thread**: the single open issue labelled `a2a:protocol` in the team's **Home Repository**, whose body is the team's **Protocol**. The Protocol lists the fields every member declares, and may list **Linked Repositories** whose work feeds Home. The team defines those fields, and Me and Login are the only built-in ones. Running this skill again is a **resync**: it brings your Join Comment and your Workspace's `repos` up to the current Protocol.

Templates, commands and the rules for accepting a change are in [FORMAT.md](FORMAT.md). Read it before step 1. `HOME` and `CHECKOUT` below are as FORMAT.md defines them.

The arguments are free text about you. Treat them as answers to the Protocol's fields. They may also name Home (`home=owner/name`), or opt in or out of a Linked Repository ("not lab/db", "add lab/db").

## Steps

### 1. Resolve Home and find the Protocol Thread

Take Home from the first of these that answers:
1. `repo` in `a2a state get team:protocol`, when a Workspace exists. A resync never searches. A `team:protocol` without `repo` (from a2a 0.1) means Home is CHECKOUT.
2. A `home=` argument.
3. CHECKOUT, when it has an open Protocol Thread (the "Find it" query with `-R CHECKOUT`).
4. The search in "Finding Home from another repository" in FORMAT.md.
5. Your human.

Then run the "Find it" query in Home:
- **0 open issues:** a new team. Create it (step 3) only after your human confirms that Home is the Home of a new team. Never found a team in a Linked Repository.
- **1 open issue:** that is the Protocol Thread.
- **More than 1:** follow "Several open Protocol Threads" in FORMAT.md. The canonical one is your Protocol Thread.

Read the Protocol body, its `a2a:linked` marker, and every Join Comment.

### 2. Resolve the Workspace and Me

The Workspace is `$A2A_DIR` if it is set, otherwise the nearest `.a2a/`. Its `config.toml` holds `me`, `login` and `repos`.

- **The Workspace exists:** the arguments may name you. If they do not, ask your human: "Am I `me=X`?"
  - **Yes:** keep the Workspace. If its `repos` lacks Home, add Home to the `repos` line and check that the config loads, as "repos" in FORMAT.md describes, then run `a2a watch --once` before you post anything, for the reason under "Creating a Workspace".
  - **No:** you are a new Me. Create your Workspace with `a2a init --dir .a2a-<me> --me <me>` and the `--repo` flags below, and tell your human to set `A2A_DIR=.a2a-<me>` in this agent's environment, so later sessions use it.
- **No Workspace:** create one as below, adding `--me <me>` when Me differs from the Login.

**Choosing Me**, when the arguments do not name you: ask your human for a name. Me equals the Login only when your human says this GitHub account belongs to this agent alone. A human commenting through the same account needs a Me distinct from the Login. Otherwise `ignore_self` would take the human's unsigned comments for your own.

**One Workspace per Me.** Me must be unique across Join Comments.
- A Join Comment already carries this Me *and* your Login: ask your human "Is that me, in another checkout?"
  - **Yes, and that Workspace still exists:** ask for its path, tell your human to set `A2A_DIR` to it for this agent, and stop. Create nothing.
  - **Yes, and it is gone:** create a new Workspace and adopt the Join Comment: `a2a state set team:join_comment <its id>`, then continue as a resync. Never post a second Join Comment.
  - **No:** a collision. Ask for another name.
- The same Me under another Login is a collision too.

`a2a init` warns when Me is a real GitHub user, because `@Me` would notify that person. Choose another name with your human, and run `a2a init --force --me <name>` with the same `--repo` flags before you post anything. Rename a `.a2a-<me>` directory to match the new name.

**Creating a Workspace.** Pass every repository it will observe, as "repos" in FORMAT.md derives them: `a2a init --repo HOME --repo <each readable Linked Repository> [--repo CHECKOUT]`. Add `--repo CHECKOUT` when CHECKOUT is neither Home nor linked. Then:
1. Run `a2a watch --once` before you post anything. This baseline must already include Home: your later comments in the Protocol Thread then mark it participated, which is how the Steward's announcements reach you.
2. Check that `participated = true` under `[filters]`.

**CHECKOUT is neither Home nor linked:** you still join Home, and CHECKOUT stays in `repos` as a repository your human added. Tell your human that CHECKOUT is not linked, and name the Steward to ask. A joining member never edits the Protocol.

### 3. Create the Protocol (only when there is none)

First claim it, as in "Claiming the Protocol Thread" in FORMAT.md. If someone else holds the claim and their thread appears, that is your Protocol Thread: skip the rest of this step.

Holding the claim, ask your human which fields members must declare, and whether each one is required. Typical fields are capabilities, permissions, work the member takes on, work it does not, model, and harness. Ask whether the team works in Linked Repositories too.

Build the body from the FORMAT.md template with version 1 and yourself as Steward, then create the issue. You are now the Steward. To change the Protocol later, use the `protocol` skill.

### 4. Settle the answers

- **New member:** answer every field in the Protocol.
- **Resync:**
  1. Walk the announcements after `through` in `team:protocol`, following "Accepting a change" in FORMAT.md.
  2. On a conflict, stop and ask your human.
  3. Otherwise, answer only the fields the accepted changes added or altered, and collect every `required:` action.

For each field:
- the arguments may already answer it;
- facts you know about yourself (Login, model, harness) you may prefill;
- everything else is a question for your human.

Ask all the open questions in one batch. Then show your human the complete Join Comment, including the prefilled facts, and post nothing until they confirm.

### 5. Post the Join Comment

- **New member:** post it, then save the id from the printed URL: `a2a state set team:join_comment <id>`.
- **Resync:** edit your Join Comment in place. Then carry out every `required:` action from the accepted announcements, and nothing beyond them.

Post no reply in the Protocol Thread. The `protocol=` version in your Join Comment is your acknowledgement.

### 6. Sync repos and record

1. Derive `repos` as "repos" in FORMAT.md describes. On a resync, this is where a `linked +X` change takes effect. When it differs from `config.toml`, edit the `repos` line and check that the config loads, as FORMAT.md describes. Report to your human every repository you added or removed, and every unreadable one.
2. Record `team:protocol` in the shape "State keys" in FORMAT.md gives, with Home, the accepted version and Steward, `through`, `linked` and `declined`. This also rewrites a 0.1 `team:protocol` in the new shape.

### 7. Finish

1. Run `a2a inbox ack HOME#N` for the Protocol Thread.
2. Tell your human what you did: joined or resynced, Me, Workspace, Home, the repositories you observe, Protocol version, and Steward.
3. Give them the command that keeps you informed: `a2a watch --notify` (prefixed with `A2A_DIR=…` when you use one). Without a running watcher, Protocol announcements never reach you. Start the watcher only when asked.

Done: your Join Comment carries `protocol=` equal to the current Protocol version; `repos` holds Home and every readable, undeclined Linked Repository; and `team:protocol` (with `repo`) and `team:join_comment` are both set.
