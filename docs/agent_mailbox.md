# Agent Mailbox: local file-based agent conversation

`scripts/agent_mailbox.py` is a small same-machine mailbox for coordinating
agents without a server. Messages, cursors, launch receipts, and attachments
are files under `data/agent_mailbox/`.

## Scope and trust boundary

- Use the mailbox for temporary coordination, handoffs, and bounded debates on
  one machine.
- Model debate is optional research discussion. It is not required for alpha
  promotion, reservation, claim, or audit; those boundaries use the
  outcome-blind D0-D3 panel and deterministic artifact hashes.
- The mailbox is gitignored and disposable. It is not a durable research
  record. Promote decisions and evidence into the experiment ticket, log, or a
  tracked artifact before cleanup.
- The launcher receipt is launcher-attested local provenance. It records which
  executable the launcher hashed and invoked; it is **not cryptographic proof**
  that a remote provider served a particular model. Another local process with
  access to the mailbox can rewrite these files.
- `from` / `--me` is a routing and display string, not identity. Structured
  identity comes from a valid launch receipt bound to role, runtime, provider,
  and run ID.
- Hashing an attachment detects later byte changes. It is not malware or
  content-safety scanning. Treat untrusted attachments as data, scan them with
  the normal local security tools, and never execute them merely because their
  digest matches.

Use the session-management channel for agents on another machine or in a
separate hosted session.

## Files and slugs

```text
data/agent_mailbox/<channel>/<seq>-<sender>.json
data/agent_mailbox/<channel>/.cursor-<agent>
data/agent_mailbox/<channel>/attachments/<name>
data/agent_mailbox/<channel>/.launch-<participant>-<run_id>.json
data/agent_mailbox/<channel>/.<participant>-exec.log
data/agent_mailbox/<channel>/.<participant>-exec.pid
```

Sequence files use atomic `O_EXCL` creation, so concurrent senders cannot
overwrite one another. Each receiver has an independent cursor.

Channel, sender, receiver, peer, role, and run-ID values are path components.
They must be ASCII slugs matching `[A-Za-z0-9][A-Za-z0-9._-]*`, at most 128
characters, and may not be Windows device names. Separators, absolute paths,
`..`, whitespace padding, drive paths, and UNC paths are rejected before a
filesystem or process action.

## Legacy messages remain supported

The original API and JSON shape are unchanged:

```python
seq = send_message("channel", "agent-a", "hello")
message = recv_message("channel", "agent-b", peer="agent-a")
```

```json
{
  "channel": "channel",
  "seq": 1,
  "from": "agent-a",
  "text": "hello",
  "ts": "2026-07-22T00:00:00+00:00"
}
```

Legacy `send`, `recv`, `transcript`, `list`, and Codex-default `dispatch`
commands keep their existing behavior. A legacy channel can pass the original
experiment-ID/path existence checks, but it is always reported as
`legacy_existence_only` and can never be marked cross-model verified.

## Basic CLI

```powershell
# Send an opener.
python scripts/agent_mailbox.py send `
  --channel exp-20260722-002-debate --me proposer --text "Please challenge this."

# Receive the next unread non-self message. Timeout exits 2; rerun recv.
python scripts/agent_mailbox.py recv `
  --channel exp-20260722-002-debate --me challenger --peer proposer --timeout 60

# Read/list/verify.
python scripts/agent_mailbox.py transcript --channel exp-20260722-002-debate
python scripts/agent_mailbox.py list
python scripts/agent_mailbox.py verify --channel exp-20260722-002-debate
```

`recv` returns the lowest sequence after the receiver's cursor that was not
sent by that receiver and, when `--peer` is supplied, came from that peer. It
advances the cursor and prints only the message text to stdout; the sender/seq
header goes to stderr.

## Structured messages

`send_message` accepts optional keyword fields without changing legacy calls:

```python
send_message(
    channel,
    display_sender,
    "challenge in attachment",
    role="challenger",
    runtime="claude",
    provider="anthropic",
    run_id="run-7bdf",
    identity_receipt=receipt,
    attachment="attachments/challenge.json",
)
```

The CLI equivalent reads the receipt from a JSON file and recomputes the
attachment hash before writing the message:

```powershell
python scripts/agent_mailbox.py send `
  --channel alpha-debate-20260722-example `
  --me claude-challenger `
  --text "challenge in attachment" `
  --role challenger `
  --runtime claude `
  --provider anthropic `
  --run-id run-7bdf `
  --identity-receipt data/agent_mailbox/exp-20260722-002-debate/.launch-claude-challenger-run-7bdf.json `
  --attachment data/agent_mailbox/exp-20260722-002-debate/attachments/challenge.json
```

Structured attachments must already exist inside that channel's
`attachments/` directory. Absolute files outside the directory, traversal,
directories, and symlinks that resolve outside the directory fail closed. The
message stores a normalized channel-relative path, byte count, and SHA-256.

## Runtime and provider receipts

The supported mapping is fixed in code and exported as
`RUNTIME_PROVIDERS`:

| Runtime | Provider |
| --- | --- |
| `codex` | `openai` |
| `claude` | `anthropic` |

`make_launch_receipt(...)` hashes the selected native executable and emits:

- `schema_version`
- `channel`, `participant`, and `role`
- `runtime` and derived `provider`
- `run_id` and random `nonce`
- resolved `executable`, `executable_sha256`, and `executable_version`
- `requested_model`
- `cross_provider_acknowledged`
- optional `initiator_runtime`
- `receipt_hash`, the canonical JSON SHA-256 of the other receipt fields

`validate_launch_receipt(...)` never raises for malformed input. It returns:

```json
{"valid": false, "errors": ["receipt_hash_mismatch"], "receipt": {}}
```

Callers can bind validation to expected channel, participant, role, runtime,
provider, and run ID. The validator re-hashes an executable that is still
present and checks runtime/provider consistency and cross-provider
acknowledgement. This is local launch provenance, not remote authentication.

## Native dispatch and model-diverse review

`dispatch` sends the opener and launches a listen-first peer in the background.
It supports native Codex and Claude CLIs. Discovery probes every candidate with
`--version`; a broken npm/batch wrapper is skipped even if it appears first on
`PATH`. Fallback discovery includes:

- known Codex desktop/cache binaries;
- `~/.vscode/extensions/openai.chatgpt-*`;
- `~/.vscode/extensions/anthropic.claude-code-*`; and
- the Windows Claude app `LocalCache/.../Claude/claude-code/*` path.

Use `--runtime-exe` to pin a native executable. `--codex-exe` remains a
backwards-compatible Codex-only alias. `--runtime auto` preserves the legacy
Codex default unless the peer name or explicit executable clearly names a
supported runtime.

The default sandbox is `workspace-write`, which is sufficient for the peer to
write its channel and attachments. Claude maps that default to `acceptEdits`;
the dangerous skip-permissions flag appears only when an operator explicitly
selects `--sandbox danger-full-access`.

An optional same-provider debate uses distinct Codex runs and at least two
requested model identities. A typical topology is Sol initiator, Terra
challenger, and a fresh Sol verifier run.

Pass `--initiator-model gpt-5.6-sol` and `--model gpt-5.6-terra` on the
challenger dispatch. Launch the verifier as another distinct participant/run,
with a model different from the challenger. Dispatch on a non-empty channel
starts that peer at its own opener rather than replaying an earlier role's task.

Codex initiator to Claude challenger:

```powershell
python scripts/agent_mailbox.py dispatch `
  --channel exp-20260722-002-debate `
  --me codex-proposer `
  --peer claude-challenger `
  --task "Challenge the frozen candidate pool; cite every load-bearing fact." `
  --initiator-runtime codex `
  --runtime claude `
  --peer-role challenger `
  --acknowledge-cross-provider `
  --rounds 3
```

Claude initiator to Codex challenger:

```powershell
python scripts/agent_mailbox.py dispatch `
  --channel alpha-debate-20260722-reverse `
  --me claude-proposer `
  --peer codex-challenger `
  --task "Challenge the proposal and identify its strongest falsifier." `
  --initiator-runtime claude `
  --runtime codex `
  --peer-role challenger `
  --acknowledge-cross-provider `
  --rounds 3
```

A launch that crosses the fixed provider mapping without
`--acknowledge-cross-provider` fails closed: no opener, receipt, PID, or child
process is created. The acknowledgement is explicit operator consent to invoke
another provider; it does not upgrade the receipt into cryptographic proof.

When `--initiator-runtime` is explicit, dispatch also discovers (or accepts
`--initiator-runtime-exe` for) the initiator's native CLI, creates a separate
initiator receipt and run ID, binds `--initiator-model` when supplied, and sends
the opener as a structured `initiator` message. `auto` retains the old legacy
opener for compatibility and therefore cannot produce an independently
verified debate channel.

Codex dispatch uses the existing `codex exec --sandbox ...` shape. Claude uses
its native noninteractive print mode and maps the mailbox sandbox choice to a
Claude permission mode. The bootstrap prompt instructs the peer to listen
first, send receipt-bound structured replies, put long bodies in hashed
attachments, avoid tracked-file edits/commits/experiment reservation, and stop
within the declared rounds.

## Verification and durable locks

```powershell
python scripts/agent_mailbox.py verify --channel alpha-debate-20260722-example
```

`verify_channel` retains the old dangling experiment-ID/path check and also:

1. canonical-hashes the ordered transcript as `transcript_sha256`;
2. resolves, reads, and hashes every structured attachment, returning an
   `attachment_sha256` map;
3. validates each structured receipt against the message's channel, role,
   runtime, provider, and run ID;
4. reports message, receipt, and attachment errors separately; and
5. sets `cross_model_verified=true` only when the whole channel is structured,
   error-free, contains both Codex/OpenAI and Claude/Anthropic launcher
   receipts, and has explicit cross-provider acknowledgement. It instead sets
   `codex_model_diverse_verified=true` when all three roles are receipt-bound
   Codex/OpenAI runs, every requested model is non-empty, and the challenger
   model differs from the initiator and verifier models.

The `initiator`, `challenger`, and `verifier` roles must use distinct run IDs
and distinct receipt participants. A challenger cannot become a verifier by
changing its sender string or reusing its run receipt. Launch or attest the
verifier as a second run and send a receipt-bound `verifier` message.

A mixed legacy/structured channel is useful for coordination but is not an
admission lock. Legacy schema-v1 `alpha_debate.py lock` artifacts can still be
validated for historical reproducibility. Current schema-v2
`alpha_search.py build-promotion` does not read the mailbox or require a debate
lock. Do not persist temporary chat as a second experiment ledger.

Existence verification still cannot detect a real but mis-attributed citation.
The verifier must open every load-bearing source and confirm the claim it is
cited for.

`requested_model` is launcher-attested metadata: its receipt hash proves that
the local launcher requested that model string, not that a remote service
cryptographically proved which weights served the run. Codex model diversity
removes cross-provider transfer friction, but is a weaker independence claim
than an OpenAI/Anthropic debate.

## Deadlock-free turn order

Agree which participant speaks first. The other listens first; thereafter both
alternate receive/send:

```text
proposer:   send A1 -> recv B1 -> send A2 -> recv B2
challenger: recv A1 -> send B1 -> recv A2 -> send B2
```

For an optional decision-support debate, name proposer, challenger, and verifier roles.
Before convergence, the challenger must steelman the proposal or state a fact
that would overturn its own position. Consensus is not a lock until the
verifier has checked every load-bearing citation and the durable artifact binds
the verified transcript and attachment hashes.

## Cleanup

Channels are temporary. After the durable ticket/log/artifact contains the
decision and its hash anchors, remove the local channel using a deliberate,
path-checked cleanup operation. Nothing under `data/agent_mailbox/` should be
treated as the only copy of research evidence.
