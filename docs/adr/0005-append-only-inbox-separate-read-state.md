# The Inbox is append-only; Read state lives in a separate file

The original spec stored `read: false` inside `inbox.jsonl` and rewrote that file on ack. That loses entries whenever `watch` appends while `ack` rewrites. Instead, only `watch` writes `inbox.jsonl`, and only by appending. Acks go to `.a2a/acks.json` under a lock, and the `read` field is computed when entries are output. As a result `.a2a/` holds one more file than the spec listed, and ack cost no longer grows with the size of the Inbox.
