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
- `docs/current_state.md`: current accepted stack, activation map, default-off
  surfaces, and known blockers.
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

## Required Preflight

Before strategy-affecting work, answer these five questions in the ticket or
working notes:

1. What is the money-making hypothesis, and is it entry, exit, ranking, capital
   allocation, LLM event scoring, or risk allocation?
2. Have we tested the same or nearby idea before? List prior experiment IDs,
   parameters, windows, and failure modes.
3. What is the single causal variable changed in this run?
4. What is the success or failure standard, and does it match
   `docs/backtesting.md`?
5. If it fails, can the next agent reproduce the run using only repository
   records?

If questions 2 through 5 cannot be answered, do not change strategy logic.

For pure measurement repair, write the blocker instead of a money-making
hypothesis. Example: "Current experiment IDs collide because artifacts can be
created before registry reservation."

## Reserve Identity First

Always reserve the experiment ID before writing runners, data directories,
artifacts, or logs. Treat this like Hugging Face Hub `create_repo`: claim the
name centrally before pushing content.

Preferred command:

```powershell
.\.venv\Scripts\python.exe -B scripts\reserve_experiment.py `
  --lane alpha_discovery `
  --hypothesis "One sentence hypothesis." `
  --change-type default_off_paper_allocation `
  --single-causal-variable "one changed variable" `
  --file-slug short_file_slug `
  --trial-family stable_trial_family `
  --changed-variable stable_changed_variable `
  --nearby-prior-experiments exp-YYYYMMDD-NNN `
  --new-evidence-type new_forward_rows
```

For measurement repair:

```powershell
.\.venv\Scripts\python.exe -B scripts\reserve_experiment.py `
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
- Do not use the dashboard `Next exp-...` value as a lock.
- To reserve a specific ID, pass `--experiment-id exp-YYYYMMDD-NNN`.
- Explicit IDs fail if the ID already appears in registry, JSONL, tickets,
  logs, cards, manifests, artifacts, data experiment paths, or runner
  filenames.

## Claim Before Work

If other agents may be active, claim the ticket:

```powershell
.\.venv\Scripts\python.exe scripts\claim_experiment.py exp-YYYYMMDD-NNN `
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
  attributable to one causal variable.

For state-surface profile, scalar, notional, or similar tuning, follow the
tighter rule in `AGENTS.md`: aggregate EV must improve by more than 10% unless
the change is pure measurement repair.

## Production/Backtest Parity

Any executable buy, sell, add, reduce, size, rank, gate, slot, heat, or LLM hard
decision must live in a shared policy path or be explicitly documented as an
allowed replay-only difference in `docs/production_backtest_parity.md`.

Do not accept a backtester-only rule.

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
.\.venv\Scripts\python.exe scripts\judge_experiment.py `
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
- hypothesis
- changed variable
- prior/nearby experiments
- parameters
- before/after/delta metrics or observed-only artifact
- production impact
- decision
- rejection reason or acceptance basis
- next retry requirements
- related files

Rejected and rolled-back experiments must still be recorded.

## Handoff Checklist

Before ending the turn, make sure the next agent can answer:

- Which ID owns the work?
- Which files were changed?
- Which single causal variable changed?
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
- Do not promote replay-only or default-off logic into live capital without a
  separate accepted activation experiment.
- Do not add LLM authority over sizing, slots, exits, or risk without replayable
  prompt/log attribution and a shared policy boundary.
