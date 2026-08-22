# exp-20260729-003 — Remove mandatory alpha debate

## Result

Accepted as experiment-process measurement repair. New alpha promotions use a
debate-free schema-v2 admission request. They no longer require another model,
a mailbox transcript, a verifier, or launcher receipts.

This does not remove deterministic admission. A new alpha/scout ticket still
requires a hash-bound promotion request that recomputes the complete
outcome-blind D0-D3 panel, proposal, selected candidate, surface/PIT readiness,
prior snapshot, artifact identities, and any pre-reservation abort. Claim,
close, and audit continue to revalidate the tracked proof.

## Compatibility and safety boundary

- Schema v2 is the default and rejects debate fields.
- Explicit legacy schema-v1 debated promotions remain readable and verifiable.
- `research_pit` remains limited to `private_replay_scout` and
  `result_ceiling=observed_only`; it cannot acquire paper/live authority.
- Novelty, saturation, recipe-lane, reopen, in-flight duplicate, Gate 1-4, and
  production-parity rules are unchanged.
- No signal, ranking, sizing, exit, order, live, or Gate-1 baseline behavior
  changed.

## Verification

- Debate-free schema-v2 focused tests: 4 passed.
- Promotion/registry/search/playbook regression set: 104 passed.
- Python compilation passed for the changed scripts.

The original prediction was directionally correct: mandatory debate was
isolated from the deterministic admission checks. The implementation retained
the promotion request rather than removing it, because it carries the D0-D3,
PIT, revocation, proposal, and artifact-integrity guarantees.
