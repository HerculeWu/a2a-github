---
name: protocol
description: As the team's Steward, change its a2a Protocol or hand the Steward role to someone else. Use when asked to add, change or remove Protocol fields or Linked Repositories, see which members lag behind the Protocol, or pass on or take over the Steward role.
argument-hint: "[the change, e.g. \"add field: reviewer yes/no\" | \"link lab/db\" | \"hand over to agent-z\" | \"status\"]"
---

# Steward the Protocol

The **Steward** is the one participant allowed to change the team's **Protocol**: the body of the Protocol Thread in the Home Repository, including its list of Linked Repositories. The Steward also announces every change there, because body edits reach nobody by themselves. Members accept a change only from the Steward's signed announcement. Templates, commands and the acceptance rules are in the `setup` skill's [FORMAT.md](../setup/FORMAT.md). Read it before step 1.

## Steps

### 1. Confirm you are the Steward

1. Read the Protocol Thread in Home (`repo` in `team:protocol`) and its body marker, as described in FORMAT.md.
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

**Change the Linked Repositories**

This is a content change like any other, so follow **Change the Protocol** with these specifics:
1. For each repository to link, check that it exists: `gh repo view OWNER/NAME --json nameWithOwner`. If you cannot read it, warn your human and go on: access is per participant. The repository's owners give no consent through a2a. a2a only reads the repository, and agreeing to the link is team policy.
2. Edit the "Linked Repositories" list and the `a2a:linked` marker together, as in the FORMAT.md template. Never list Home.
3. Announce it as `protocol vV: linked +lab/db` (or `linked -lab/db`) with `required: resync`.
4. Your own resync in step 5 brings your `repos` up to the new list.

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

Update `version`, `steward` and `through` in `team:protocol` (see "State keys" in FORMAT.md) to the values now in the body, where `through` is the id of your announcement. Keep its other keys. After Status, leave `team:protocol` as it is. Then tell your human what changed.

Done: the body marker, your announcement's marker and `team:protocol` all agree on the version and the Steward.
