# Experiment Ticket Schema

This file defines the minimum contract for multi-agent experiments. The goal is
to let agents explore in parallel while preserving one baseline, one judge, and
one causal variable per experiment.

Primary index:

- `docs/experiment_registry.json`

Per-experiment state:

- `docs/experiments/tickets/exp-*.json`
- `docs/experiments/logs/exp-*.json`

The registry is intentionally only a small index. Each agent mostly writes its
own ticket and final log file, so parallel experiments do not fight over one
large shared JSON document.

## Status Values

- `proposed`: ticket exists, no agent owns it yet.
- `claimed`: an agent owns the ticket and may start work inside the allowed scope.
- `running`: work is actively being evaluated.
- `accepted`: judge result passed the acceptance rule.
- `rejected`: judge result failed the acceptance rule.
- `observed_only`: analysis/instrumentation result with no strategy acceptance claim.
- `stale`: ticket should not be continued without refreshing the baseline.

## Lanes

- `alpha_discovery`: new entry, exit, ranking, allocation, or strategy hypothesis.
- `loss_attribution`: bad-trade source analysis and failure taxonomy.
- `universe_scout`: new ticker universe, candidate source, or external alpha source.
- `measurement_repair`: replay, attribution, data snapshot, or production/backtest parity work.

## Required Ticket Fields

```json
{
  "experiment_id": "exp-20260425-001",
  "status": "proposed",
  "lane": "loss_attribution",
  "owner": null,
  "hypothesis": "Breakout losses cluster in one reproducible follow-through failure mode.",
  "change_type": "analysis_only",
  "single_causal_variable": "breakout follow-through taxonomy",
  "baseline_result_file": "data/backtest_results_20260425.json",
  "allowed_write_scope": [
    "quant/experiments/exp_20260425_001_breakout_follow_through_taxonomy.py",
    "data/experiments/exp-20260425-001/exp_20260425_001_breakout_follow_through_taxonomy.json",
    "docs/experiments/tickets/exp-20260425-001.json",
    "docs/experiments/logs/exp-20260425-001.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json"
  ],
  "must_not_touch": [
    "quant/constants.py",
    "quant/signal_engine.py"
  ],
  "locked_variables": [
    "breakout follow-through taxonomy"
  ],
  "evaluation_windows": [
    {
      "start": "2025-10-23",
      "end": "2026-04-21"
    }
  ],
  "acceptance_rule": "observed_only; must produce reproducible bad-trade taxonomy",
  "production_impact": {
    "shared_policy_changed": false,
    "backtester_adapter_changed": false,
    "run_adapter_changed": false,
    "replay_only": false,
    "parity_test_added": false
  },
  "created_at": "2026-04-25T00:00:00-07:00",
  "claimed_at": null,
  "completed_at": null,
  "result": null
}
```

## Acceptance Rule

For strategy-affecting experiments, `scripts/judge_experiment.py` uses the
repository gate:

- `expected_value_score` improves by more than 10%, or
- Sharpe improves by more than 0.1, or
- max drawdown falls by more than 1 percentage point, or
- total PnL improves by more than 5%, or
- trade count increases while win rate does not decline.

Measurement and analysis tickets may be marked `observed_only`, but they must
still record the artifact that makes the next alpha experiment more testable.

## Production Impact Rule

Every ticket that can affect executable trade behavior must include
`production_impact`. The fields mean:

| Field | Meaning |
| --- | --- |
| `shared_policy_changed` | A shared decision module or strategy constant changed. |
| `backtester_adapter_changed` | Historical replay wiring changed. |
| `run_adapter_changed` | Daily production wiring, report, JSON, or prompt exposure changed. |
| `replay_only` | The difference is an allowed historical-data limitation, not duplicate strategy logic. |
| `parity_test_added` | A focused test or manifest update guards the production/backtest contract. |

If `shared_policy_changed=true`, then either `run_adapter_changed=true` or
`replay_only=true` must be true. Otherwise the experiment is backtester-only and
must not be accepted. Allowed replay-only differences are listed in
`docs/production_backtest_parity.md`.

Example observed-only closeout:

```powershell
python scripts\judge_experiment.py `
  --experiment-id exp-20260425-001 `
  --before data\backtest_results_20260424.json `
  --after data\backtest_results_20260425.json `
  --status-override observed_only `
  --change-summary "Recorded a reproducible loss taxonomy." `
  --append-log `
  --write-registry
```

`--append-log` writes the generated row to
`docs/experiments/logs/<experiment_id>.json`. Duplicate experiment IDs are
rejected unless `--allow-duplicate-log-id` is set.

## Conflict Rules

`scripts/claim_experiment.py` blocks a claim when another active ticket
(`claimed` or `running`) overlaps either:

- `allowed_write_scope`, or
- `locked_variables`.

The shared coordination files below are ignored for scope conflicts because
every agent needs them for closeout:

- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`

Actual writes to those files are still protected by lock files:

- `docs/experiment_log.jsonl.lock`
- `docs/experiment_registry.json.lock`

The scripts wait for the lock by default and recover stale locks after the
configured stale-lock window. Use `--lock-timeout-seconds` to fail faster in a
busy multi-agent run.

Use narrow write scopes. A broad scope such as `quant/` should be treated as
exclusive ownership of that whole area.

## Automatic Write Scopes

`scripts/create_experiment_ticket.py` now generates per-experiment write scopes
when `--allowed-write-scope` is omitted. This is the default for parallel
agents because the script knows the assigned `experiment_id` and can create
non-overlapping paths:

- `quant/experiments/<experiment_id_as_prefix>_<slug>.py`
- `data/experiments/<experiment_id>/<experiment_id_as_prefix>_<slug>.json`
- `docs/experiments/tickets/<experiment_id>.json`
- `docs/experiments/logs/<experiment_id>.json`
- `docs/experiment_log.jsonl`
- `docs/experiment_registry.json`

The default `<slug>` is derived from `--single-causal-variable`, so a ticket
with `single_causal_variable="bad trade hold-quality taxonomy"` creates names
like `exp_20260427_010_bad_trade_hold_quality_taxonomy.py`. If an agent wants
a shorter explicit name, pass `--file-slug hold_quality_audit`.

Do not use broad directory scopes such as `data/`, `quant/`, `docs/`, or
`scripts/` for ordinary experiments. They serialize unrelated agents because
claim conflict detection treats parent and child paths as overlapping. The
ticket creation script rejects those broad scopes unless
`--exclusive-scope-ok` is passed.

When a custom scope is needed but the experiment id is not known yet, use
templates:

```powershell
python scripts\create_experiment_ticket.py `
  --lane alpha_discovery `
  --hypothesis "One narrow shadow source." `
  --change-type new_strategy_shadow `
  --single-causal-variable "one shadow source" `
  --allowed-write-scope "quant/experiments/{experiment_id}_{lane}.py,data/experiments/{experiment_id}/{change_type}.json"
```
