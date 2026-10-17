# Participants sharing one Login are told apart by Signatures, added with `a2a sign`

One human often runs several agents under their own GitHub account, so every comment from them shows the same Login. Without a way to tell them apart, an agent would receive its own comments and the `participated` rule could not work. Posted text therefore carries a Signature: a visible `<sub>— NAME</sub>` line, followed by a hidden `<!-- a2a:from=NAME -->` marker. Only the hidden marker is parsed, and text without a Signature is attributed to the Login itself. a2a adds one primitive, `a2a sign`, which reads a body on stdin and writes the signed body to stdout, e.g. `… | a2a sign | gh issue comment 5 -F -`. Writes still go only through `gh`, and a2a never posts to GitHub itself.

## Considered Options

- **No attribution under a shared Login**: rejected. It breaks `ignore_self` and `participated` exactly where they matter most.
- **A Signature convention without a helper**: rejected. One forgotten Signature makes an agent receive its own message, which can start a self-reply loop.
- **An `a2a post` command that writes to GitHub**: rejected. It duplicates `gh` and would need a flag for every kind of write.

## Consequences

A Signature is not authentication: any collaborator can forge one, which is acceptable inside one trusted repository. The mode is not a setting. A Workspace is in shared-Login mode exactly when `me` differs from `login`. In that mode `assignee` is meaningless and is warned against, and `participated` is accumulated locally rather than backfilled through search.
