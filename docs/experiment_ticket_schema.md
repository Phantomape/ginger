# Experiment Ticket Schema

This file defines the minimum contract for multi-agent experiments. The goal is
to let agents explore in parallel while preserving one baseline, one judge, and
one causal variable per experiment.

Primary registry:

- `docs/experiment_registry.json`

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
    "docs/",
    "scripts/"
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

## Conflict Rules

`scripts/claim_experiment.py` blocks a claim when another active ticket
(`claimed` or `running`) overlaps either:

- `allowed_write_scope`, or
- `locked_variables`.

Use narrow write scopes. A broad scope such as `quant/` should be treated as
exclusive ownership of that whole area.
