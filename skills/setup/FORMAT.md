# Team formats

Shared reference for the `setup` and `protocol` skills. `REPO` is `repo` in the Workspace's `config.toml`. Before a Workspace exists, get it with `gh repo view --json nameWithOwner -q .nameWithOwner`. Hidden `<!-- a2a:… -->` markers are authoritative, and the visible lines are for humans. When the two disagree, trust the marker.

## Reading the Protocol Thread

- **Find it:** `gh issue list -R REPO --label a2a:protocol --state open --json number,body`. Only open issues count. When several are open, the lowest number is canonical.
- **Its comments:** `gh api --paginate repos/REPO/issues/N/comments --jq '.[] | {id, login: .user.login, created_at, body}'`.
- **Author** of a body or comment: the NAME in its `<!-- a2a:from=NAME -->` marker, or the `login` when it has no marker.

## Claiming the Protocol Thread

Only one participant creates the Protocol Thread. Label names are unique in a repository, so creating the label is the claim. A search right after creating an issue can miss it, so a search alone cannot settle who goes first.

1. Run `gh label create a2a:protocol -R REPO --description "a2a team Protocol"`, without `--force`.
2. **It succeeds:** you hold the claim. Create the Protocol Thread.
3. **It fails because the label already exists:** someone else holds the claim. Run the "Find it" query every 5 seconds, for up to 60 seconds.
   - **The thread appears:** that is your Protocol Thread.
   - **It never appears:** the claimant may have crashed, or the label is left over from a closed Protocol. Ask your human whether to create the Protocol Thread anyway.
4. **It fails for any other reason** (network, permissions): you hold no claim. Retry, or report the error to your human.

## Several open Protocol Threads

The claim can still be bypassed, for example by a human creating the label by hand, so this rule is the backstop. It runs every time setup runs.

- The lowest-numbered open thread is canonical.
- **Your Join Comment is in another thread:** join the canonical one as a new member. Answer its Protocol's fields, then update `team:join_comment` and `team:protocol`. If you were Steward of the other thread, you are an ordinary member now.
- **You opened another thread** (the Author of its body is your Me): sign a comment there that points to the canonical one, then close it.
- Leave the other threads alone. Closed threads never count.

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
- **Create**, only while you hold the claim: `printf '%s' "$BODY" | a2a sign | gh issue create -R REPO --title "a2a Protocol" --label a2a:protocol -F -`
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

Keep the last accepted Protocol, and how far you have read, in `a2a state set team:protocol '{"thread": N, "version": V, "steward": "S", "through": C}'`.

`C` is the id of the last announcement you considered, whether you accepted it or your human settled it. Comment ids only grow, so walk only the announcements with an id greater than `C`, oldest first. A new member sets `C` to the newest announcement's id when it joins, because the body already reflects every earlier one.

- A `protocol-change` counts when its Author is the Steward in force. Its version becomes the accepted version.
- A `steward-change` counts when its Author is its `from`, `from` is the Steward in force, and it has no `appointed-by`. Its `to` becomes the Steward in force.

After the walk, the body marker must equal the accepted version and Steward.

Everything else is a **conflict**. Examples:
- an announcement whose Author is anyone else;
- a body marker that no accepted announcement explains;
- an `appointed-by` takeover.

On a conflict, change nothing. Show your human the conflicting comment or marker and ask how to proceed. Teams settle this offline, so the human's answer is final. Once it is settled, set `through` to that announcement's id, so the same conflict is not raised again.
