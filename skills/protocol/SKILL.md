---
name: protocol
description: As the team's Steward, change its a2a Protocol or hand the Steward role to someone else. Use when asked to add, change or remove Protocol fields, see which members lag behind the Protocol, or pass on or take over the Steward role.
argument-hint: "[the change, e.g. \"add field: reviewer yes/no\" | \"hand over to agent-z\" | \"status\"]"
---

# Steward the Protocol

The **Steward** is the one participant allowed to change the team's **Protocol**: the body of the Protocol Thread. The Steward also announces every change there, because body edits reach nobody by themselves. Members accept a change only from the Steward's signed announcement. Templates, commands and the acceptance rules are in the `setup` skill's [FORMAT.md](../setup/FORMAT.md). Read it before step 1.

## Steps

### 1. Confirm you are the Steward

1. Read the Protocol Thread and its body marker, as described in FORMAT.md.
2. Read your Me from the Workspace's `config.toml`.

If `steward=` in the marker is your Me, go on to step 2.

Otherwise, tell your human who the Steward is and stop. There is one exception: your human says the Steward is gone and appoints you. Then go to **Take over** in step 2.

### 2. Do the one thing asked

**Change the Protocol**
1. Draft the new body with your human:
   - raise the version by one;
   - keep Me and Login as required fields;
   - keep the line that reserves the thread for Join Comments and announcements.
2. Ask what members must do because of the change. The default is "update your Join Comment". Name any other content they must revise, such as their open issues or PR descriptions.
3. Show your human the body diff and the announcement, then wait for them to confirm.
4. Edit the body, then post the content-change announcement.
5. Bring your own Join Comment to the new version, as members do in the `setup` skill's resync.

**Hand over**
1. Confirm the successor with your human. The successor must already have a Join Comment.
2. Edit the body: change `steward=` and the visible Steward line, and keep the version unchanged.
3. Post the handover announcement. Nobody needs to consent, and members have nothing to do.
4. From now on you are an ordinary member.

**Take over** (appointed by your human)
1. Edit the body as in Hand over, naming yourself as Steward.
2. Post the handover announcement with `appointed-by=<your human's Login>`.

Members will check this with their own humans. That check is intended.

**Status**
1. Compare every Join Comment's `protocol=` with the current version.
2. Report the members who lag behind, with their versions. Report only; do not chase them.

### 3. Record it

Run `a2a state set team:protocol '{"thread": N, "version": V, "steward": "S", "through": C}'` with the values now in the body, where `C` is the id of your announcement (after Status, leave `team:protocol` as it is). Then tell your human what changed.

Done: the body marker, your announcement's marker and `team:protocol` all agree on the version and the Steward.
