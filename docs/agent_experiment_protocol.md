# Agent Experiment Protocol

This is the operational entrypoint for agents running experiments in this
repository. It links the durable rules in `AGENTS.md` to the concrete files and
commands used during day-to-day work.

Use this document as the first checklist before changing strategy behavior,
creating a paper sleeve, running a replay, repairing measurement, or writing an
experiment artifact.

## Source Of Truth Map

- `AGENTS.md`: top-level agent rules, required reading, and Gate 1-4.
- `docs/backtesting.md`: canonical backtest command, windows, baseline metrics,
  and acceptance evidence.
- `docs/alpha_context_pack.md`: default compact LLM memory for alpha search,
  current priorities, frozen retry zones, and lesson-card links.
- `docs/current_state_snapshot.md`: default compact current-state entrypoint,
  recent accepted/default-off state, and exact-source pointers.
- `docs/current_state.md`: legacy full exact-state reference for accepted stack,
  activation map, default-off surfaces, and known blockers. Read targeted
  sections when exact state details are needed; do not use it as the default
  memory dump.
- `docs/alpha-optimization-playbook.md`: preferred alpha directions, frozen
  retry zones, and mechanism-level lessons.
- `docs/data_edge_context_layers.md`: passive context, sidecar, attribution, and
  data-edge surfaces.
- `docs/production_backtest_parity.md`: production/backtest parity contract.
- `docs/experiment_ticket_schema.md`: ticket fields, statuses, lanes, and
  conflict rules.
- `docs/experiment_log_format.md`: final JSON/JSONL record shape.
- `docs/experiment_dashboard.md`: local UI, ID reservation, and identity
  diagnostics.

Do not copy protocol details into multiple files. If a command, window, metric,
or parity rule conflicts with a source file above, the source file wins.

## Layered Experiment Memory

Experiment memory is intentionally layered:

- Raw facts live in per-experiment tickets, logs, cards, artifacts, data files,
  and committed code.
- `docs/experiment_registry.json` is only a light coordination/index surface.
  It should not become the durable research-memory database.
- `docs/alpha_context_pack.md` is the default short memory surface for LLM
  agents.
- `docs/lessons/*.md` cards store compact mechanism-level lessons for targeted
  retrieval.
- `docs/current_state_snapshot.md` is the short current-state entrypoint.
- `docs/current_state.md` is a full reference for exact accepted-stack and
  activation details, not the default context to paste into every run. It can
  be archived only after those exact-state duties have audited replacements.

After closing a material alpha experiment, refresh the compact memory:

```powershell
.\.venv\Scripts\python.exe -B scripts\build_alpha_memory.py --git-ref HEAD
```

The generated context pack and lesson cards are derived summaries. If a
summary conflicts with a ticket, log, artifact, code, `docs/backtesting.md`,
`docs/current_state.md`, or `docs/production_backtest_parity.md`, the
raw/source file wins.

## Experiment Classes

`alpha_search` changes or tests a money-making hypothesis:

- entry
- exit
- ranking
- capital allocation
- risk allocation
- LLM event scoring boundary
- candidate pool or universe promotion
- paper-sleeve activation or sizing

`measurement_repair` fixes whether alpha can be trusted or reproduced:

- ID reservation and registry coverage
- data coverage, replay, or attribution repair
- production/backtest parity repair
- dashboard or audit visibility
- required field logging
- forward outcome or replacement-value ledger quality

Measurement repair is allowed to interrupt alpha work only when it removes a
real blocker to credible alpha evaluation or production execution.

## Lean Alpha Contract

For alpha work, prefer one compact contract over scattered form-filling. The
contract can live in the ticket, experiment card, artifact, or log, but it must
be easy for the next agent to find.

Minimum content:

- Hypothesis inference: why this mechanism should make money, what related
  experiments imply, and the most likely failure modes.
- Fixed policy bundle: the one decision hypothesis under test, plus which
  edits are only helper, replay, daily-output, parity, live-realism, artifact,
  or test work needed to evaluate it.
- Measurement plan: the standard windows, before/after metric, production
  consistency boundary, and live-realistic envelope when relevant.
- Reflection plan: what result would reject the idea, what near-neighbor retry
  should be forbidden, and what new evidence would make a retry worthwhile.

If those four blocks cannot be answered, do not change strategy logic. Do not
block an experiment merely because low-value accounting fields are incomplete
when the tools can default them and the contract above is specific.

For pure measurement repair, write the blocker instead of a money-making
hypothesis. Example: "Current experiment IDs collide because artifacts can be
created before registry reservation."

## Causal Granularity

`single_causal_variable` is a legacy field name. Treat it as the single
attributable decision hypothesis or policy bundle under test, not as one code
parameter, one file, or one mechanical wiring step.

Allowed inside one experiment:

- shared helper implementation;
- historical replay and daily default-off snapshot functions;
- report, ledger, or run-path observe-only wiring that calls the same helper;
- parity tests and production/backtest contract updates;
- fixed execution envelope fields such as notional, cap, costs, liquidity,
  slippage, displacement, exposure limits, and kill switch;
- artifact, ticket, card, manifest, and log updates.

These are not separate causal variables when they are required to evaluate the
same pre-declared policy bundle.

Not allowed inside one ordinary experiment:

- adding two unrelated alpha sources;
- changing entry and exit rules at the same time unless the pre-declared object
  is a complete lifecycle policy and no component-level claim is made;
- tuning several thresholds after seeing results;
- accepting a composite policy while later claiming one internal component was
  independently proven.

If a composite policy is intentional, predeclare it as the causal bundle, list
its fixed components, and judge only the bundle. To learn which component works,
run a predeclared ablation or factorial follow-up; do not infer it after the
fact.

## Shared-Paper-First Fast Path

For high-potential, production-visible candidate-pool or default-off paper alpha,
prefer a shared-paper-first experiment instead of a private replay scout.

Use this path when the proposed signal depends only on fields that can be
available in both historical replay and the daily run, such as free OHLCV,
official event calendars, accepted default-off sleeve snapshots, Companyfacts
rows with filed-date boundaries, FINRA/SEC rows with publication-date
boundaries, or already-produced core entry context.

Minimum requirements:

- Reserve one `alpha_search` ID for the shared helper experiment.
- Implement the candidate logic in a shared helper module, typically
  `quant/<alpha_name>_paper_sleeve.py`, before writing private runner-only
  selection code.
- The helper should expose both a historical replay function and a daily
  default-off snapshot function, for example `build_*_historical_trades()` and
  `build_*_paper_sleeve_snapshot()`.
- The experiment runner must call the shared helper for after-measurement; it
  should not duplicate a second private candidate implementation.
- Add focused tests proving daily snapshot and historical replay share the same
  rule version and produce the same representative candidate on a fixture.
- Daily report, ledger, or run-path observe-only wiring may be included in the
  same experiment when it calls the same helper, keeps `trade_enabled=False`,
  and leaves live/default orders, ranking, sizing, exits, and watchlists
  unchanged.
- If the alpha is intended to become live-capital eligible, define and measure
  the live-realistic execution envelope in this same experiment: intended
  notional, capital cap, liquidity/slippage assumptions, portfolio displacement,
  exposure limits, kill switch, order semantics, and failure handling.
- Keep `trade_enabled=False` and live/default orders unchanged.
- Record the helper in `docs/production_backtest_parity.md` when Gate 4 accepts
  or when the helper is retained for forward default-off observation.

If Gate 4 accepts, the result may be recorded as an accepted shared default-off
helper. A separate follow-up experiment is not required merely to wire
observe-only daily/report output when that wiring was included in the same
ticket and reuses the same helper. If the accepted helper does not yet expose
daily output, the next step can be a small forward-paper wiring experiment.
Live trading, capital allocation, core ranking, exits, watchlists, or order
surfaces require live-realistic evidence. If the accepted experiment already
measured that execution envelope and the release does not change it, enabling
`trade_enabled=True` can be a release checklist/config change, not a new alpha
experiment. If the execution envelope was not measured, run a narrow
activation-envelope Gate 1-4 that tests only the missing capital/execution/risk
constraints and does not search for a new signal.

Private replay scouts remain allowed only when the data shape is uncertain or
the idea is too speculative to justify a helper. A positive private scout is not
an accepted alpha; it must be labeled as a replay lead, explain why
shared-paper-first was not used, and name the exact shared helper/parity work
required before any paper or production observation.

## Reserve Identity First

Always reserve the experiment ID before writing runners, data directories,
artifacts, or logs. Treat this like Hugging Face Hub `create_repo`: claim the
name centrally before pushing content.

Preferred command:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py new `
  --lane alpha_search `
  --hypothesis "One sentence hypothesis." `
  --change-type default_off_paper_allocation `
  --decision-variable "one decision hypothesis or fixed policy bundle" `
  --causal-components "shared helper,daily snapshot,parity test" `
  --file-slug short_file_slug `
  --nearby-prior-experiments exp-YYYYMMDD-NNN `
  --success-probability 0.35 `
  --main-failure-modes "thin_sample,concentration_failed" `
  --confidence-reason "Mechanism, prior evidence, and disconfirmers."
```

Use `--trial-family`, `--changed-variable`, `--prior-trial-count`, and
`--new-evidence-type` when they add real meta-learning value. Do not stop a
good alpha test just to overfit those labels; the tooling has defaults.

For measurement repair:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py new `
  --lane measurement_repair `
  --hypothesis "Repair the blocker that makes alpha evaluation unreliable." `
  --change-type identity_or_measurement_repair `
  --single-causal-variable "the repaired measurement surface" `
  --file-slug measurement_repair_slug
```

Rules:

- Use the returned `experiment_id` everywhere.
- Reservation automatically writes the ticket, an experiment card, and a
  revision manifest.
- `alpha_search`, `alpha_discovery`, and `universe_scout` tickets are rejected
  by code unless they include pre-run `success_probability` and
  `main_failure_modes`.
- Do not use the dashboard `Next exp-...` value as a lock.
- To reserve a specific ID, pass `--experiment-id exp-YYYYMMDD-NNN`.
- Explicit IDs fail if the ID already appears in registry, JSONL, tickets,
  logs, cards, manifests, artifacts, data experiment paths, or runner
  filenames.

## Claim Before Work

If other agents may be active, claim the ticket:

```powershell
.\.venv\Scripts\python.exe scripts\experiment.py claim exp-YYYYMMDD-NNN `
  --owner your-agent-name
```

The claim system blocks overlapping active work by `allowed_write_scope` and
`locked_variables`. Do not bypass a conflict unless you understand why the
other active ticket cannot touch the same behavior.

## Gate 1: Baseline

Use `docs/backtesting.md` for the canonical command, windows, and artifacts.

A valid baseline must record:

- protocol and windows
- artifact path
- `expected_value_score`
- return, Sharpe, drawdown, trade count, win rate, survival rate
- known data or parity limitations

If no valid baseline exists, create the baseline first. Do not change strategy
logic before baseline evidence is available.

## Gate 2: Field Reality Check

List every field the rule depends on and verify it exists in the runtime path
that will use it.

Minimum checks for position lifecycle work:

- `entry_date` in `operator_inputs/open_positions.json`
- `target_price` in `operator_inputs/open_positions.json`

For LLM-assisted work, verify the dimension is present in the prompt, logs, and
decision chain. Do not let the LLM rely on implicit knowledge for hard trading
decisions.

## Gate 3: Survival Audit

Check `signals_generated`, `signals_survived`, and `survival_rate` from the
backtest output.

Rules:

- If `survival_rate < 5%`, do not add filters.
- If a new filter sharply lowers survival, require direct evidence.
- Prefer replacing, loosening, or merging an existing filter over stacking
  another broad gate.
- Use measured values, not theoretical estimates.

## Gate 4: After Measurement

Run the same canonical protocol after the change. Compare before and after using
the same windows and metrics.

Default retention logic:

- Strong keep: clear `expected_value_score` improvement without unacceptable
  drawdown, tail, trade-count, or survival regression.
- Conditional keep: measurement repair that fixes evaluation, reproducibility,
  logging, parity, or production execution, even if EV is unchanged.
- Default reject: main objective declines, risk worsens, only one window wins,
  most windows regress, complexity rises without evidence, or the result is not
  attributable to one predeclared decision hypothesis or policy bundle.

For state-surface profile, scalar, notional, or similar tuning, follow the
tighter rule in `AGENTS.md`: aggregate EV must improve by more than 10% unless
the change is pure measurement repair.

## Production/Backtest Parity

Any executable buy, sell, add, reduce, size, rank, gate, slot, heat, or LLM hard
decision must live in a shared policy path or be explicitly documented as an
allowed replay-only difference in `docs/production_backtest_parity.md`.

Do not accept a backtester-only rule.

For default-off paper alpha, do not retain a high-potential positive result if
the only implementation is private runner logic. Either start with the
shared-paper-first path above, or downgrade the result to
`positive_replay_lead_not_promoted` until a shared helper reproduces it.

A shared-paper-first result is not backtester-only merely because the daily path
does not trade it. It must, however, expose the same rule through a daily
default-off snapshot, report, or ledger path and keep `trade_enabled=False`.

Do not mark an alpha `live_ready` unless the experiment measured a
live-realistic execution envelope. Paper EV without notional, liquidity,
slippage, portfolio displacement, and kill-switch constraints is an accepted
observation surface, not a live strategy.

When changing shared behavior, add focused parity tests or update the parity
contract. Production output must expose the same action or decision basis that
the backtester uses.

## Artifact Discipline

Every experiment should keep artifacts under the reserved ID:

```text
quant/experiments/exp_YYYYMMDD_NNN_<slug>.py
data/experiments/exp-YYYYMMDD-NNN/<slug>.json
experiments/artifacts/exp-YYYYMMDD-NNN_<slug>.md
experiments/tickets/exp-YYYYMMDD-NNN.json
experiments/cards/exp-YYYYMMDD-NNN.md
experiments/manifests/exp-YYYYMMDD-NNN.json
experiments/logs/exp-YYYYMMDD-NNN.json
```

The card is the human-readable experiment summary. The revision manifest is the
machine-readable reproducibility snapshot: git revision, dirty status, baseline
file hash when available, ticket hash, and card hash. Regenerate or update the
manifest after final artifacts exist if exact after-run hashes are required.

Do not write broad files outside the ticket's `allowed_write_scope` unless the
ticket explicitly allows it and the change is necessary.

## Closeout

For before/after JSON files, use:

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

For observed-only measurement or analysis work, add:

```powershell
  --status-override observed_only
```

Final records must include:

- experiment ID
- hypothesis inference and fixed policy bundle
- nearby experiments or a clear statement that no close prior was found
- before/after/delta metrics or observed-only artifact
- production impact
- decision
- rejection reason or acceptance basis, with post-run reflection
- next retry requirements or explicit "do not retry without X"
- related files

Rejected and rolled-back experiments must still be recorded.

Run the process audit when reconciling legacy tickets or dashboard gaps:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py audit
```

Use `--strict` in automation to fail only on post-enforcement alpha/scout
prediction or calibration gaps. Pre-enforcement history is reported as legacy
process debt and should not be backfilled with hindsight probabilities.

Use lean strict audit for active alpha automation:

```powershell
.\.venv\Scripts\python.exe -B scripts\experiment.py audit --lean-strict
```

This does not demand more accounting fields. It blocks post-lean-enforcement alpha
tickets with weak/generic `confidence_reason` or closed alpha logs that leave
post-run reflection as `TODO`, missing, or too vague. Existing historical debt
is reported as legacy quality debt; do not waste alpha time backfilling it.

## Handoff Checklist

Before ending the turn, make sure the next agent can answer:

- Which ID owns the work?
- Which files were changed?
- Which single decision hypothesis or policy bundle was tested?
- Which baseline and after artifacts were used?
- Which tests or backtests were run?
- Was this alpha evidence, observed-only evidence, or measurement repair?
- What is blocked, rejected, accepted, or next?

If any answer is missing, write it into the ticket, log, artifact, or final
response before stopping.

## Hard No

- Do not start with a hand-written experiment ID.
- Do not create runner or artifact files before ID reservation.
- Do not change strategy behavior without Gate 1-4.
- Do not keep failed strategy logic just because unit tests pass.
- Do not use paper PnL alone as activation evidence.
- Do not call a private replay-only scout "accepted"; accepted paper alpha needs
  shared replay/daily semantics or a documented measurement-repair exception.
- Do not promote replay-only or default-off logic into live capital without a
  separate accepted activation experiment.
- Do not add LLM authority over sizing, slots, exits, or risk without replayable
  prompt/log attribution and a shared policy boundary.
