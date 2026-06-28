# Agent Mailbox — file-based agent-to-agent conversation

A minimal, file-driven channel so two (or more) agents running **on the same
machine** can talk by listening to each other. No server, no shared memory —
just atomic files, the same idiom as ticket reservation. Tool:
[`scripts/agent_mailbox.py`](../scripts/agent_mailbox.py).

## When to use / when not to

- **Use it** for live coordination between concurrent agents on this machine:
  hand off a sub-task, ask the agent holding a ticket a question, negotiate who
  takes which lane, debate a decision before committing.
- **Do NOT use it** for cross-machine or persistent record-keeping. Messages are
  **local and gitignored** (`data/agent_mailbox/` is not tracked) — on purpose.
  Tracking an append-only chat is exactly what caused the `experiment_log.jsonl`
  merge conflicts this repo retired (see `experiment.py rebuild-log`). For a
  durable decision, write it to the experiment ticket/log, not here. For agents
  in *other* sessions/machines, use the session-management channel, not files.
- Listening is **polling** (1s), so latency is ~1s, not instant.
- Both participants must be alive and looping. An agent that exits cannot be
  talked to.

## Where messages live

```
data/agent_mailbox/<channel>/<seq>-<sender>.json   # one atomic message file
data/agent_mailbox/<channel>/.cursor-<agent>       # each agent's read cursor
```

- A **channel** is just a directory; pick a descriptive name, e.g.
  `next-priority-20260628` or `exp-20260628-002-handoff`.
- **seq** is a per-channel global sequence (`0001`, `0002`, …) allocated
  lock-free via `O_EXCL`; concurrent senders never collide or overwrite.
- Each agent has a **cursor** tracking the last message it has read, so you just
  alternate `send`/`recv` without tracking sequence numbers by hand.

## CLI

```powershell
# Send a message (prints the allocated seq)
python scripts/agent_mailbox.py send --channel C --me A --text 'hello B'

# Block until the next message addressed to you (not your own); prints its text.
# Exits with code 2 on timeout (default 100s) -- just re-run the same recv.
python scripts/agent_mailbox.py recv --channel C --me A
python scripts/agent_mailbox.py recv --channel C --me A --peer B   # only from B
python scripts/agent_mailbox.py recv --channel C --me A --timeout 60

# Read the whole conversation in order; list channels
python scripts/agent_mailbox.py transcript --channel C
python scripts/agent_mailbox.py list
```

`recv` returns the lowest-sequence message past your cursor that you did **not**
send (optionally filtered to `--peer`), advances your cursor, and prints the
text to stdout (a `[from=… seq=…]` header goes to stderr). Messages you sent are
skipped automatically.

## How to participate (deadlock-free turn recipe)

Two agents, 5 rounds. The rule that prevents both sides from waiting at once:
**one agent speaks first; the other listens first.** After that, each agent
simply alternates `recv` then `send`.

Agent **A** (speaks first):
```
send  --channel C --me A --text '<opener>'
recv  --channel C --me A          # read B's reply
send  --channel C --me A --text '<reply>'
recv  --channel C --me A
... (repeat until done)
```

Agent **B** (listens first):
```
recv  --channel C --me B          # read A's opener
send  --channel C --me B --text '<reply>'
recv  --channel C --me B
send  --channel C --me B --text '<reply>'
... (repeat until done)
```

This yields the interleaving `A1, B1, A2, B2, …` with no deadlock: whenever one
side calls `recv`, the other has already sent or is about to. End by agreeing on
a turn count up front (e.g. "5 rounds then stop") or by sending a final message
that says you are done.

More than two agents share a channel the same way; use `--peer` when you need to
wait for a specific sender rather than "anyone but me".

## Conventions

- **Names**: pick a stable, unique `--me` (e.g. your lane + id: `alpha-explore`,
  `measurement-repair`, or an experiment owner name).
- **Channel naming**: `<purpose>-<YYYYMMDD>` or `<exp-id>-<purpose>`.
- **Message text**: keep it short; plain text. When invoking via a shell, avoid
  embedding the quote character you used to wrap `--text`.
- **Cleanup**: channels are disposable local files; delete the channel directory
  when a conversation is finished. Nothing here is part of the durable record —
  promote any decision into the experiment ticket/log.
