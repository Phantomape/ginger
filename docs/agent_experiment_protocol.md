# Agent Experiment Protocol

Operational runbook for experiments. Durable rules live in `AGENTS.md`;
canonical metrics and windows live in `docs/backtesting.md`; production parity
lives in `docs/production_backtest_parity.md`. This file tells agents which
commands to run and what an experiment must leave behind.

## Source Map

- `AGENTS.md`: top-level rules, priority, required startup questions.
- `docs/backtesting.md`: Gate 1-4 commands, windows, baselines, metrics.
- `docs/alpha_context_pack.md`: compact alpha memory for current runs.
- `docs/current_state_snapshot.md`: compact current-state entrypoint.
- `docs/alpha-optimization-playbook.md`: alpha directions and frozen zones.
- `docs/production_backtest_parity.md`: shared policy and adapter parity.
- `docs/data_edge_context_layers.md`: context, attribution, data-edge surfaces.
- `docs/experiment_ticket_schema.md`: ticket fields and conflict rules.
- `docs/experiment_log_format.md`: JSON / JSONL closeout shape.

If sources conflict, the more specific source wins. Do not copy full rules into
multiple docs.

## Standard Workflow

1. Read the startup sources from `AGENTS.md`.
2. Answer the five pre-run questions in the ticket, card, artifact, or log.
3. Reserve an ID before writing runner, artifact, data, ticket, or log files.
4. Claim the ticket before work when other agents may be active.
5. Implement the single predeclared decision hypothesis or policy bundle.
6. Run Gate 1-4 with the canonical protocol in `docs/backtesting.md`.
7. Record production impact and parity boundary.
8. Write artifact, log, card, ticket, manifest, and JSONL closeout.
9. Run `scripts/experiment.py audit --lean-strict`.
10. Commit when the task or automation requires a committed experiment result.

## Reserve

Preferred command:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py new `
  --lane alpha_search `
  --hypothesis "One sentence hypothesis." `
  --change-type candidate_pool_full_stack `
  --decision-variable "single decision hypothesis or fixed policy bundle" `
  --causal-components "shared helper,daily snapshot,parity test" `
  --file-slug short_slug `
  --nearby-prior-experiments exp-YYYYMMDD-NNN `
  --success-probability 0.35 `
  --main-failure-modes "thin_sample,concentration_failed,not_incremental" `
  --confidence-reason "Mechanism, prior evidence, and disconfirmers."
```

Use `--change-type candidate_pool_full_stack` for high-potential,
production-visible default-off candidate-pool or paper-sleeve alpha unless the
data shape is genuinely uncertain.

For measurement repair:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py new `
  --lane measurement_repair `
  --hypothesis "Repair the blocker that makes alpha evaluation unreliable." `
  --change-type identity_or_measurement_repair `
  --decision-variable "the repaired measurement surface" `
  --file-slug repair_slug
```

Reservation writes the ticket, card, and manifest. Explicit IDs must not collide
with registry, JSONL, tickets, logs, cards, manifests, artifacts, data paths, or
runner filenames.

## Claim

Preferred command:

```powershell
.\.venv\Scripts\python.exe scripts\experiment.py claim exp-YYYYMMDD-NNN `
  --owner your-agent-name
```

`scripts/experiment.py claim` delegates to `scripts/claim_experiment.py`, which
checks active ticket conflicts by `allowed_write_scope` and `locked_variables`.
Do not bypass a conflict unless you can prove the active work cannot touch the
same behavior.

## Lean Alpha Contract

An alpha experiment must leave four compact blocks:

- Hypothesis inference: why this should make money, related experiments, and
  likely failure modes.
- Fixed policy bundle: the one decision hypothesis, plus which edits are only
  helper, replay, daily output, parity, live-realism, artifact, or test work.
- Measurement plan: standard windows, before/after metrics, production
  consistency boundary, and execution envelope when relevant.
- Reflection: why the result happened, forbidden near-neighbor retries, and
  what new evidence would justify another attempt.

Do not split a single policy bundle merely to satisfy old field names.
`single_causal_variable` means one attributable decision hypothesis, not one
file or one parameter.

## Shared-Paper-First

Use shared-paper-first when the signal can be available in both historical
replay and daily production observation: free OHLCV, official event calendars,
accepted default-off sleeve snapshots, filed-date bounded fundamentals,
publication-date bounded FINRA/SEC rows, or produced core-entry context.

Minimum implementation:

- one shared `quant/<alpha_name>_paper_sleeve.py` helper;
- one historical replay function, usually `build_*_historical_trades()`;
- one daily snapshot function, usually `build_*_paper_sleeve_snapshot()`;
- experiment runner calls the shared helper for after-measurement;
- daily/report/ledger wiring calls the same helper and keeps `trade_enabled=False`;
- focused parity test proving replay and daily semantics share rule version and
  representative candidate behavior;
- production parity entry when Gate 4 accepts or the helper is retained for
  forward default-off observation.

Positive private replay scouts are allowed only when data shape is uncertain or
the idea is too speculative to justify a helper. A positive scout must be
recorded as `positive_replay_lead_not_promoted`, explain why shared-paper-first
was skipped, and name the exact helper/parity work required.

## Full-Stack Candidate-Pool Path

For candidate-pool alpha, prefer the one-shot full-stack path:

- Template: `quant/experiments/_templates/candidate_pool_full_stack_template.py`
- Verdict helper: `quant/full_stack_candidate_pool.py`
- Change type: `candidate_pool_full_stack`

Verdicts:

- `reject`: Gate 4 fails. Roll back strategy logic and log the failure.
- `accepted_paper_pending_forward`: Gate 4 passes. Default-off paper sleeve is
  accepted; remaining live blockers are forward-row maturation and Gate 5
  checklist items.
- `live_eligible`: Gate 4 and Gate 5 pass. Live enablement is a config or
  release change behind the declared envelope and kill switch.

An incomplete execution envelope blocks only `live_eligible`; it does not block
`accepted_paper_pending_forward`. Declare the envelope up front anyway.

## Gate Execution

Use `docs/backtesting.md` for all Gate 1-4 details. Do not duplicate window,
metric, baseline, or acceptance numbers here.

Quick reminders:

- Gate 1: baseline exists and is readable.
- Gate 2: runtime fields exist; minimum position fields are `entry_date` and
  `target_price`.
- Gate 3: survival is measured; do not add filters below the survival floor.
- Gate 4: same canonical windows before/after; `pytest` is not a substitute.

## Closeout

For before/after JSON artifacts:

```powershell
.\.venv\Scripts\python.exe scripts\experiment.py close `
  --experiment-id exp-YYYYMMDD-NNN `
  --before path\to\before.json `
  --after path\to\after.json `
  --write-registry `
  --log-draft `
  --append-log `
  --change-summary "What changed in one sentence."
```

Self-registering runners must use
`experiment_registry.persist_self_registered_result()`. They must not write
`docs/experiment_registry.json` directly.

Final records must include:

- experiment ID and lane;
- fixed hypothesis or policy bundle;
- nearby history;
- before/after/delta metrics or observed-only artifact;
- production impact and parity boundary;
- decision and acceptance/rejection basis;
- post-run reflection and next evidence;
- related files and reproduction command.

Rejected experiments still need a complete record.

## Artifacts

Keep files under the reserved ID:

```text
quant/experiments/exp_YYYYMMDD_NNN_<slug>.py
data/experiments/exp-YYYYMMDD-NNN/<slug>.json
experiments/tickets/exp-YYYYMMDD-NNN.json
experiments/cards/exp-YYYYMMDD-NNN.md
experiments/manifests/exp-YYYYMMDD-NNN.json
experiments/logs/exp-YYYYMMDD-NNN.json
docs/experiment_log.jsonl
docs/experiment_registry.json
```

Do not write broad files outside the ticket's `allowed_write_scope` unless the
ticket explicitly allows it and the change is necessary.

## Audit

Active alpha automation should run:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py audit --lean-strict
```

`lean_quality_passed` is the actionable verdict. Historical debt is visibility
only unless the audit says it blocks current post-enforcement work.

Self-registration guard:

- New runners must not write registry/ticket files by hand.
- Use `experiment.py new/close` or `persist_self_registered_result()`.
- `quant/test_no_new_self_registering_runners.py` and audit self-registration
  output surface new offenders.

## Handoff Checklist

Before stopping, the next agent should know:

- Which ID owns the work?
- Which files changed?
- Which single decision hypothesis or policy bundle was tested?
- Which baseline and after artifacts were used?
- Which tests/backtests ran?
- Was this alpha evidence, observed-only evidence, measurement repair, or docs
  maintenance?
- What is accepted, rejected, blocked, or next?

## Hard No

- Do not start with a hand-written experiment ID.
- Do not create runner/artifact files before reservation.
- Do not change strategy behavior without Gate 1-4.
- Do not keep failed strategy logic because unit tests pass.
- Do not call private replay-only scouts accepted alpha.
- Do not promote default-off logic into live capital without a live-realistic
  execution envelope and accepted activation evidence.
- Do not give LLM authority over sizing, slots, exits, or risk without
  replayable prompt/log attribution and a shared policy boundary.
