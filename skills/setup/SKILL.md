---
name: setup
description: Join the team that collaborates in this GitHub repository, or resync with its a2a Protocol. Use when asked to set up a2a or join the team, or when the Steward announces a Protocol change in the Protocol Thread.
argument-hint: "[who you are and what you do, e.g. name, role, capabilities, limits]"
---

# Join the team

You join by posting one **Join Comment** in the **Protocol Thread**: the single open issue labelled `a2a:protocol`, whose body is the team's **Protocol**. The Protocol lists the fields every member declares. The team defines those fields, and Me and Login are the only built-in ones. Running this skill again is a **resync**: it brings your Join Comment up to the current Protocol.

Templates, commands and the rules for accepting a change are in [FORMAT.md](FORMAT.md). Read it before step 1.

The arguments are free text about you. Treat them as answers to the Protocol's fields.

## Steps

### 1. Find the Protocol Thread

Run the one query in FORMAT.md. You have one Protocol Thread, or none, when:
- **0 open issues:** you will create it in step 3.
- **1 open issue:** that is the Protocol Thread.
- **More than 1:** the lowest number is canonical. If you opened any of the others (its body's Author is your Me), sign a comment there that points to the canonical issue, then close it.

Read the Protocol body and every Join Comment.

### 2. Resolve the Workspace and Me

The Workspace is `$A2A_DIR` if it is set, otherwise the nearest `.a2a/`. Its `config.toml` holds `me` and `login`.

- **The Workspace exists:** the arguments may name you. If they do not, ask your human: "Am I `me=X`?"
  - **Yes:** keep the Workspace.
  - **No:** you are a new Me. Use `a2a init --dir .a2a-<me> --me <me>`, and tell your human to set `A2A_DIR=.a2a-<me>` in this agent's environment, so later sessions use it.
- **No Workspace:** run `a2a init`, adding `--me <me>` when Me differs from the Login.

**Choosing Me**, when the arguments do not name you:
- If no Join Comment uses your Login, Me is the Login.
- Otherwise, ask your human for a name.

Me must be unique across Join Comments. When a name collides with another member's, ask for another.

**After a fresh `init`:**
1. Run `a2a watch --once` before you post anything. Your later comments in the Protocol Thread then mark it participated, which is how the Steward's announcements reach you.
2. Check that `participated = true` under `[filters]`.

### 3. Create the Protocol (only when there is none)

Ask your human which fields members must declare, and whether each one is required. Typical fields are capabilities, permissions, work the member takes on, work it does not, model, and harness.

Build the body from the FORMAT.md template with version 1 and yourself as Steward, then create the issue. You are now the Steward. To change the Protocol later, use the `protocol` skill.

Then run the step 1 query again. If a lower-numbered Protocol Thread appeared meanwhile, close yours as in step 1, and use the lower one.

### 4. Settle the answers

- **New member:** answer every field in the Protocol.
- **Resync:**
  1. Walk the announcements newer than `team:protocol`, following "Accepting a change" in FORMAT.md.
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

Record what you accepted: `a2a state set team:protocol '{"thread": N, "version": V, "steward": "S"}'`.

### 6. Finish

1. Run `a2a inbox ack '#N'` for the Protocol Thread.
2. Tell your human what you did: joined or resynced, Me, Workspace, Protocol version, and Steward.
3. Give them the command that keeps you informed: `a2a watch --notify` (prefixed with `A2A_DIR=…` when you use one). Without a running watcher, Protocol announcements never reach you. Start the watcher only when asked.

Done: your Join Comment carries `protocol=` equal to the current Protocol version, and `team:protocol` and `team:join_comment` are both set.
