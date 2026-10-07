# Cross-lane experiment identity repair

The old allocator could give two worktrees the same experiment number. The repair reads IDs from sibling paths and Git ref tree names, then holds a common Git-directory OS lock until the ticket is durable. Local cache refresh remains outside that lock. Root and Edge received the same semantic patch without replacing their different registry implementations.

## Verification

- Both frozen old implementations reproduced occupied-ID selection; both installed implementations skip those IDs.
- Root: 23 targeted tests passed. Edge: 27 targeted tests passed.
- Seven new tests cover real two-process worktree reservation, live/untracked IDs, ref-only IDs and explicit refusal, ref updates, detached HEAD, retry/cache-lock behavior, and a non-Git fixture under a Git repository.
- Both historical exp-20260826-001 UID/ticket byte hashes match the parent-provided pre-close references. These references were recorded during this work unit, not represented as an earlier historical snapshot.
- Live readback found 2,737 occupied IDs from each lane; Edge sees root's exp-20260906-001 and 002, and root sees Edge-only identities.

## Result and limits

Accepted measurement repair. The downstream collision check is open for a fresh scout reservation. Economic progress remains false for this repair; no financial result, strategy setting, capital allocation, or trading permission changed. Normal local scans took 31-45 seconds, so the shared lock waits at least 120 seconds; the old scan was otherwise preserved. Writers must use the installed reserve API to participate in the lock.

The exp002 force claim bypassed only the shared immutable trade-permissions label, with disjoint actual file scopes and no permission edits. Raw historical evidence was not moved or replaced.

Detailed proof: data/experiments/exp-20260906-002/before.json, after.json, verification.json. Reproduce with verify_repair.py and the targeted pytest command recorded in after.json.
