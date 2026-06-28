# Agent Experiment Protocol

Operational runbook for experiments. Durable rules live in `AGENTS.md`;
canonical metrics and windows live in `docs/backtesting.md`; production parity
lives in `docs/production_backtest_parity.md`, with adapter rows in
`docs/production_backtest_parity_matrix.md`. This file tells agents which
commands to run and what an experiment must leave behind.

## Source Map

- `AGENTS.md`: top-level rules, priority, required startup questions.
- `docs/backtesting.md`: Gate 1-4 commands, windows, baselines, metrics.
- `docs/alpha_context_pack.md`: compact alpha memory for current runs.
- `docs/current_state_snapshot.md`: compact current-state entrypoint.
- `docs/alpha-optimization-playbook.md`: current alpha directions and frozen zones.
- `docs/lessons/*.md`: generated mechanism evidence cards.
- `docs/alpha_external_research_map.md`: research-literature idea map.
- `docs/production_backtest_parity.md`: core shared-policy parity contract.
- `docs/production_backtest_parity_matrix.md`: per-adapter parity rows.
- `docs/experiment_ticket_schema.md`: ticket fields and conflict rules.
- `docs/experiment_log_format.md`: JSON / JSONL closeout shape.

If sources conflict, the more specific source wins. Do not copy full rules into
multiple docs.

## Standard Workflow

1. Read the startup sources from `AGENTS.md`.
2. Answer the five pre-run questions in the ticket, card, artifact, or log.
3. Reserve an ID before writing runner, artifact, data, ticket, or log files.
4. Claim the ticket before work when other agents may be active.
5. For production-visible candidate-pool or paper-sleeve alpha, use the
   full-stack candidate-pool contract by default.
6. Implement the single predeclared decision hypothesis or policy bundle.
7. Run Gate 1-4 with the canonical protocol in `docs/backtesting.md`.
8. Record production impact and parity boundary.
9. Write artifact, log, card, ticket, manifest, and JSONL closeout.
10. Run `scripts/experiment.py audit --lean-strict`.
11. Commit when the task or automation requires a committed experiment result.

## Reserve

Default alpha-search reservation for production-visible candidate-pool or
paper-sleeve ideas:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py new `
  --lane alpha_search `
  --hypothesis "One sentence hypothesis." `
  --change-type candidate_pool_full_stack `
  --decision-variable "single decision hypothesis or fixed policy bundle" `
  --causal-components "shared helper,historical replay,daily snapshot,parity test,execution envelope,full-stack verdict" `
  --file-slug short_slug `
  --nearby-prior-experiments exp-YYYYMMDD-NNN `
  --success-probability 0.35 `
  --main-failure-modes "thin_sample,concentration_failed,not_incremental" `
  --confidence-reason "Mechanism, prior evidence, and disconfirmers."
```

Use `--change-type candidate_pool_full_stack` as the default for
production-visible default-off candidate-pool or paper-sleeve alpha. Choose a
different alpha change type only when the decision variable is not a
candidate-pool source, paper sleeve, source allocator, or replacement-value
route. Mark the ticket `implementation_mode=private_replay_scout` only when the
data shape is genuinely uncertain or the idea is too speculative to justify the
shared helper up front; record that escape reason before running the scout.

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

### Novelty Check (near-neighbor guard)

`experiment.py new` runs a near-neighbor check against
`docs/frozen_families.jsonl` (regenerate with
`scripts/build_frozen_families.py`). It infers the proposed decision-fingerprint
and prints the nearest frozen/explored families to stderr; stdout stays clean
ticket JSON.

It is **blocking by default for alpha lanes** (`alpha_search`,
`alpha_discovery`, `universe_scout`): if the proposal is a near-neighbor of a
frozen/explored family, the reservation is refused (before any ID is allocated)
unless you pass `--novelty-override --new-evidence-axis "<what is genuinely
new>"` — a new data source, a field no prior family used, a new gate shape, or
forward replacement rows. The override is recorded on the ticket. Other lanes
(e.g. `measurement_repair`) are never blocked.

Escape hatches: `--no-enforce-novelty` makes a single reservation warn-only;
`GINGER_NOVELTY_GATE=off` (or `warn`/`0`) disables blocking globally,
`=block`/`1` forces it. The check fails safe — if the tooling/registry is
missing it silently skips. Check ad hoc with
`scripts/check_experiment_novelty.py --describe "..." --trial-family ...`.

### Source-saturation gate (anti-field-churn)

The near-neighbor gate sees each new field as a distinct fingerprint, so it
cannot stop the "scan yet another single field on the same data source" churn:
each swap looks novel even when the source has been tried dozens of times and
almost never accepted. The **source-saturation gate** is a second, independent
block for exactly that pattern.

On a `candidate_pool` (scan-shape) reservation it rolls up every prior family
sharing the proposal's `(gate_shape, data_source)` from
`docs/frozen_families.jsonl`. If that source has been tried enough and almost
never paid out (default: **trials ≥ 12 and accept rate ≤ 5%**) it is `saturated`
and the alpha-lane reservation is **refused**. As of 2026-06-21 this blocks new
candidate-pool scans on `companyfacts_ratio` (3/84), `sec_text_event` (0/38),
`form4_insider` (0/13), and `revision_expectation` (1/24); it leaves live cells
open — `finra_short_interest` (4/15), `ohlcv_momentum`, `ohlcv_relation` — plus
all non-scan shapes (`allocator_source`, `notional_scalar`). The point is to
push searches off proven-dry sources, not to stop alpha search.

Override is deliberately a **separate** flag from `--novelty-override` (so it is
not waved through by reflex): pass `--saturated-source-override` **and**
`--new-evidence-axis "<a new data source/field never scanned on this shape, not
another field on the same dry source>"`. The override is recorded on the ticket
for audit. Thresholds are env-tunable: `GINGER_SATURATION_MIN_TRIALS` (default
12) and `GINGER_SATURATION_MAX_ACCEPT` (default 0.05). Fails safe and applies
only to scan-shape alpha lanes. Inspect ad hoc with the same
`scripts/check_experiment_novelty.py` invocation — it now prints a
`Source saturation:` line.

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

For production-visible candidate-pool alpha, those four blocks should be
satisfied through the full-stack candidate-pool contract by default: shared
helper, historical replay, daily default-off snapshot, parity test, declared
execution envelope, Gate-4 verdict, and closeout artifact in one experiment.
If any of those pieces are skipped, the record must explain the blocker and the
result cannot be called accepted alpha merely because a replay was positive.

## Prediction Enforcement

Prediction-required lanes are `alpha_search`, `alpha_discovery`, and
`universe_scout`. Use `experiment.py new` / `reserve` or
`persist_self_registered_result()` so the code can enforce prediction metadata
before work is recorded.

Required pre-run fields:

- `prediction.success_probability`
- `prediction.main_failure_modes`
- `prediction.confidence_reason`

`confidence_reason` must be substantive: explain the money-making mechanism,
nearby historical evidence, and main disconfirming risk. Placeholder text and
too-short reasons are rejected at reservation/self-registration time.

At closeout, keep the prediction on the final record and include calibration or
reflection explaining whether the predicted failure mode occurred. Run
`scripts/experiment.py audit --lean-strict`; weak prediction quality and weak
reflection block the lean verdict, while legacy missing prediction/calibration
debt remains visibility-only.

## Shared-Paper-First

Use shared-paper-first when the signal can be available in both historical
replay and daily production observation: free OHLCV, official event calendars,
accepted default-off sleeve snapshots, filed-date bounded fundamentals,
publication-date bounded FINRA/SEC rows, or produced core-entry context.
For candidate-pool alpha, the default runnable form of shared-paper-first is
the full-stack candidate-pool contract below.

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

## Data-Edge Promotion

Concrete data surfaces, sidecars, sleeves, attribution scripts, artifact
schemas, and meta-research tools live in code, tests, experiment artifacts, and
generated lessons. Use `rg` over `quant/`, `experiments/`, and `data/` when
selecting a concrete surface.

Before a context field can affect entry, exit, ranking, sizing, orders, or live
capital, answer:

1. Is the field produced in production, not only in a research script?
2. Is the field saved in an append-only, replayable daily artifact?
3. Does the backtester have point-in-time access to it?
4. Has attribution shown monotonic or otherwise interpretable predictive value?
5. Does the proposed change alter only one independent decision hypothesis?
6. Does the change pass `docs/backtesting.md` Gate 1-4?
7. Is the experiment recorded whether accepted or rejected?

If the answer to 1-4 is no, keep the field read-only and continue accumulating
history. If the field is already PIT-safe, replayable, and easy for daily output
to emit, do not force passive-only staging; start the serious test as a
shared-paper-first helper.

## Full-Stack Candidate-Pool Contract

For production-visible candidate-pool alpha, the one-shot full-stack contract
is the default experiment specification, not a follow-up promotion path. Start
here when the candidate source can be computed point-in-time and exposed by the
daily default-off path.

- Template: `quant/experiments/_templates/candidate_pool_full_stack_template.py`
- Verdict helper: `quant/full_stack_candidate_pool.py`
- Change type: `candidate_pool_full_stack`

The contract bundles:

- one fixed candidate-pool decision hypothesis or source-allocation policy;
- one shared helper used by both historical replay and daily default-off output;
- one replay path that measures the after result on canonical windows;
- one daily snapshot, report, or ledger path that exposes the same rule version
  with `trade_enabled=False`;
- one focused parity test for representative candidate behavior;
- one declared live-realistic execution envelope, even if live is not eligible;
- one full-stack verdict recorded through `quant/full_stack_candidate_pool.py`
  or an equivalent artifact block.

The scout-then-adapter two-round split is the exception, allowed only when the
data shape is genuinely uncertain. A positive replay scout must be promoted
through this same contract - shared sleeve, parity tests, declared execution
envelope, full-stack verdict - not through an ad hoc adapter-only follow-up.

Verdicts:

- `reject`: Gate 4 fails. Roll back strategy logic and log the failure.
- `accepted_paper_pending_forward`: Gate 4 passes. Default-off paper sleeve is
  accepted; remaining live blockers are forward-row maturation and Gate 5
  checklist items.
- `live_eligible`: Gate 4 and Gate 5 pass. Live enablement is a config or
  release change behind the declared envelope and kill switch.

An incomplete execution envelope blocks only `live_eligible`; it does not block
`accepted_paper_pending_forward`. Declare the envelope up front anyway.

Gate-4 evaluation note: `evaluate_gate4` includes the AGENTS.md scout
materiality floor (>= $500 average per-trade PnL delta or >= 5pp average return
delta). That floor is calibrated for support-field / notional-scalar scouts on
existing sleeves; at the fixed $4,000 paper notional used by candidate-pool
adapters it would reject every accepted comparator (for example
exp-20260608-013 at roughly $51/trade). For new candidate-pool sources, run
`evaluate_gate4` both ways - strict (`check_materiality=True`) for the record
and canonical (`check_materiality=False`) for the decision - and treat beating
the closest accepted comparator after costs as the binding materiality
standard. Record both blocks in the artifact.

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
docs/experiment_registry.json
```

The per-experiment log shard `experiments/logs/exp-YYYYMMDD-NNN.json` is the
source of truth. Do **not** write the monolithic `docs/experiment_log.jsonl`: it
is an untracked, derived view regenerated from the shards with
`experiment.py rebuild-log`. Writing it directly is what caused divergent-append
merge conflicts; new runners must only write their shard.

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
