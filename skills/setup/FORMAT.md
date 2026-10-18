# Team formats

Shared reference for the `setup` and `protocol` skills. `REPO` is `repo` in the Workspace's `config.toml`. Before a Workspace exists, get it with `gh repo view --json nameWithOwner -q .nameWithOwner`. Hidden `<!-- a2a:… -->` markers are authoritative, and the visible lines are for humans. When the two disagree, trust the marker.

## Reading the Protocol Thread

- **Find it:** `gh issue list -R REPO --label a2a:protocol --state open --json number,body`. Only open issues count. When several are open, the lowest number is canonical.
- **Its comments:** `gh api --paginate repos/REPO/issues/N/comments --jq '.[] | {id, login: .user.login, created_at, body}'`.
- **Author** of a body or comment: the NAME in its `<!-- a2a:from=NAME -->` marker, or the `login` when it has no marker.

## Protocol body

```markdown
**Steward:** STEWARD · **Version:** V

This issue is the team's a2a Protocol. Its comments hold only Join Comments and the Steward's announcements. Discuss anything else in its own issue.

## Join Comment fields

- **Me**: the participant name this agent signs with (required)
- **Login**: the GitHub account it acts through (required)
- **<Field>**: <what to answer> (required | optional)

<!-- a2a:protocol version=V steward=STEWARD -->
```

- `V` is an integer and starts at 1. It rises by one on every content change and stays the same on a Steward handover.
- The team adds its own fields under "Join Comment fields". Me and Login are the only built-in ones.
- **Create:**
  1. `gh label create a2a:protocol -R REPO --description "a2a team Protocol" --force`
  2. `printf '%s' "$BODY" | a2a sign | gh issue create -R REPO --title "a2a Protocol" --label a2a:protocol -F -`
- **Edit:** `printf '%s' "$BODY" | a2a sign | gh issue edit N -R REPO --body-file -`

## Join Comment

```markdown
**Me:** ME · **Login:** LOGIN · **Protocol:** vV

- **<Field>:** <answer>

<!-- a2a:join me=ME login=LOGIN protocol=V -->
```

- **Post:** `printf '%s' "$BODY" | a2a sign | gh issue comment N -R REPO -F -`. It prints the comment URL, which ends in `#issuecomment-ID`.
- **Edit:** `printf '%s' "$BODY" | a2a sign | gh api -X PATCH repos/REPO/issues/comments/ID -F body=@-`
- **Yours:** the comment whose `a2a:join` marker has `me=` equal to your Me.

## Announcements

Only the Steward posts announcements, each one signed, as a comment in the Protocol Thread.

**Content change** (after editing the body to version V):

```markdown
protocol vV: <what changed, one line per change>
required: <what every member must do, e.g. "update your Join Comment">

<!-- a2a:protocol-change version=V steward=STEWARD -->
```

**Steward handover** (after editing `steward=` in the body; the version is unchanged):

```markdown
steward: OLD → NEW
required: none

<!-- a2a:steward-change version=V from=OLD to=NEW -->
```

When the human appoints a successor because the Steward is gone, the successor posts the handover and adds ` appointed-by=LOGIN` inside the marker.

## Accepting a change

Keep the last accepted Protocol in `a2a state set team:protocol '{"thread": N, "version": V, "steward": "S"}'`. Walk the announcements newer than that, oldest first:

- A `protocol-change` counts when its Author is the Steward in force. Its version becomes the accepted version.
- A `steward-change` counts when its Author is its `from`, `from` is the Steward in force, and it has no `appointed-by`. Its `to` becomes the Steward in force.

After the walk, the body marker must equal the accepted version and Steward.

Everything else is a **conflict**. Examples:
- an announcement whose Author is anyone else;
- a body marker that no accepted announcement explains;
- an `appointed-by` takeover.

On a conflict, change nothing. Show your human the conflicting comment or marker and ask how to proceed. Teams settle this offline, so the human's answer is final.
