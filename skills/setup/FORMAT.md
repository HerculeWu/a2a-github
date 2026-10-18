# Team formats

Shared reference for the `setup` and `protocol` skills. Hidden `<!-- a2a:… -->` markers are authoritative, and the visible lines are for humans. When the two disagree, trust the marker.

- `HOME` is the Home Repository, `owner/name`: the repository that holds the Protocol Thread and the team's deliverable. Once setup has run, it is `repo` in `team:protocol`.
- `CHECKOUT` is the repository of the current directory: `gh repo view --json nameWithOwner -q .nameWithOwner`. It may be Home, a Linked Repository, or neither.
- Every Protocol Thread command passes `-R HOME`, and every reply passes `-R owner/name` of its Thread, because the checkout may be another repository. Write every Thread as `owner/name#N`.

## Reading the Protocol Thread

- **Find it:** `gh issue list -R HOME --label a2a:protocol --state open --json number,body`. Only open issues count. When several are open, the lowest number is canonical.
- **Its comments:** `gh api --paginate repos/HOME/issues/N/comments --jq '.[] | {id, login: .user.login, created_at, body}'`.
- **Author** of a body or comment: the NAME in its `<!-- a2a:from=NAME -->` marker, or the `login` when it has no marker.
- **A read that fails** (a non-zero `gh` exit, a network error, or empty output where a body or marker must be) tells you nothing. In particular, it never means "no Protocol Thread", "not the Steward" or "no announcements". Retry it, and if it keeps failing, report the error to your human and stop.

## Claiming the Protocol Thread

Only one participant creates the Protocol Thread. Label names are unique in a repository, so creating the label is the claim. A search right after creating an issue can miss it, so a search alone cannot settle who goes first.

1. Run `gh label create a2a:protocol -R HOME --description "a2a team Protocol"`, without `--force`.
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

## Linked Repositories

- OWNER/NAME: <purpose, optional>

<!-- a2a:linked repos=OWNER/NAME,OWNER/NAME -->

<!-- a2a:protocol version=V steward=STEWARD -->
```

- `V` is an integer and starts at 1. It rises by one on every content change and stays the same on a Steward handover.
- The team adds its own fields under "Join Comment fields". Me and Login are the only built-in ones. When the Protocol lists Linked Repositories, "the Linked Repositories you work in" is a typical field to suggest.
- **Linked Repositories** are the repositories whose work feeds Home's deliverable. The `a2a:linked` marker is the list; the visible lines and their purposes are for humans. Home is never listed. With no marker, or `repos=` empty, there are none: leave the whole section out of a single-repository Protocol. Nothing is ever written in a Linked Repository.
- **Create**, only while you hold the claim: `printf '%s' "$BODY" | a2a sign | gh issue create -R HOME --title "a2a Protocol" --label a2a:protocol -F -`
- **Edit:** `printf '%s' "$BODY" | a2a sign | gh issue edit N -R HOME --body-file -`

## Join Comment

```markdown
**Me:** ME · **Login:** LOGIN · **Protocol:** vV

- **<Field>:** <answer>

<!-- a2a:join me=ME login=LOGIN protocol=V -->
```

- **Post:** `printf '%s' "$BODY" | a2a sign | gh issue comment N -R HOME -F -`. It prints the comment URL, which ends in `#issuecomment-ID`.
- **Edit:** `printf '%s' "$BODY" | a2a sign | gh api -X PATCH repos/HOME/issues/comments/ID -F body=@-`
- **Yours:** the comment whose `a2a:join` marker has `me=` equal to your Me.
- A Join Comment declares nothing about repositories unless the Protocol asks for it in a field of its own. It never changes `repos`.

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

Keep the last accepted Protocol, and how far you have read, in `team:protocol` (see [State keys](#state-keys)).

`C`, its `through`, is the id of the last announcement you considered, whether you accepted it or your human settled it. Comment ids only grow, so walk only the announcements with an id greater than `C`, oldest first. A new member sets `C` to the newest announcement's id when it joins, because the body already reflects every earlier one.

- A `protocol-change` counts when its Author is the Steward in force. Its version becomes the accepted version.
- A `steward-change` counts when its Author is its `from`, `from` is the Steward in force, and it has no `appointed-by`. Its `to` becomes the Steward in force.

After the walk, the body marker must equal the accepted version and Steward.

Everything else is a **conflict**. Examples:
- an announcement whose Author is anyone else;
- a body marker that no accepted announcement explains;
- an `appointed-by` takeover.

On a conflict, change nothing. Show your human the conflicting comment or marker and ask how to proceed. Teams settle this offline, so the human's answer is final. Once it is settled, set `through` to that announcement's id, so the same conflict is not raised again.

## Finding Home from another repository

When the checkout has no open Protocol Thread, search for a Protocol that links it:

```bash
gh search issues --label a2a:protocol --state open "CHECKOUT" --json repository,number,body
```

Search is fuzzy, so verify each candidate: keep it only when the `a2a:linked` marker in its body lists CHECKOUT exactly, ignoring case. The candidate's `repository.nameWithOwner` is then Home.
- **One verified match:** that is Home. It shows in the Join Comment preview, which your human confirms anyway.
- **Several:** two Projects claim this repository. Ask your human which one is Home.
- **None:** ask your human for Home.

## repos

`repos` in `config.toml` lists the repositories your Workspace observes. Derive it from GitHub facts, never from a Join Comment:

1. **Home**, always. Announcements reach you through Home even when you work only in a Linked Repository.
2. **Every Linked Repository** in the `a2a:linked` marker that your Login can read: `gh repo view OWNER/NAME --json nameWithOwner` exits 0. Report the unreadable ones to your human and leave them out. Probe them again on every resync, so access granted later is picked up.
3. **Minus `declined`**: Linked Repositories your human opted out of.
4. **Plus every repository already in `repos` that is not in `linked`.** Your human added those, and setup never removes them. CHECKOUT, when it is neither Home nor linked, is one of them.

A Linked Repository leaves `linked` only when the Protocol stops listing it; then remove it from `repos` too. When your human deletes a linked repository from `repos` by hand, or says "not lab/db" in setup's arguments, add it to `declined`. Only an explicit setup argument, such as "add lab/db", takes it out of `declined` again.

**Writing `repos`.** The first `a2a init` passes every repository: `a2a init --repo HOME --repo OWNER/NAME …`. After that, `config.toml` is your human's file. Edit only its `repos = [...]` line, in place, keeping every other line and comment:

```toml
repos = ["lab/paper", "lab/sim"]
```

Then run `a2a inbox count` once. It loads the config, so a non-zero exit means the edit broke it: put the previous line back and report the error to your human.

## State keys

```bash
a2a state set team:protocol '{"repo": "HOME", "thread": N, "version": V, "steward": "S", "through": C, "linked": [...], "declined": [...]}'
a2a state set team:join_comment ID
```

- `repo`: Home.
- `thread`, `version`, `steward`: the Protocol Thread's number and the last accepted Protocol.
- `through`: the id of the last announcement considered, accepted or settled (see [Accepting a change](#accepting-a-change)).
- `linked`: the Linked Repositories setup added to `repos`.
- `declined`: the Linked Repositories your human opted out of.

A `team:protocol` without `repo` was written by a2a 0.1: its Home is CHECKOUT. Resync rewrites it in the shape above.

Keep reading positions per Thread as `read:owner/name#N`.
