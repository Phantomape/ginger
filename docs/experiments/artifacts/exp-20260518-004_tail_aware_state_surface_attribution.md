# exp-20260518-004 Tail-Aware State-Surface Attribution

Decision: `observed_only_no_new_strategy_variable`.

Read-only diagnostics. Core strategy logic, default-off state-surface policy, and live/default orders were not changed.

## Core Control

| Window | EV | PnL | Sharpe | Max DD | Trades | Survival | Control |
|---|---:|---:|---:|---:|---:|---:|---|
| late_strong | 5.1628 | $117,072.92 | 4.41 | 6.65% | 18 | 80.39% | PASS |
| mid_weak | 2.1402 | $78,110.11 | 2.74 | 11.19% | 21 | 79.25% | PASS |
| old_thin | 0.5911 | $39,667.96 | 1.49 | 10.01% | 22 | 86.67% | PASS |

## Tail Comparison

| Variant | Trades | EV delta vs control | PnL delta vs control | PnL top-5 | PnL HHI | Gate hard failures |
|---|---:|---:|---:|---:|---:|---|
| flat_top5 | 24 | +1.6715 | $+33,900.97 | 57.52% | 0.0903 | none |
| rank_notional | 24 | +2.1620 | $+44,019.10 | 60.16% | 0.0936 | pnl_top5_concentration |
| hold_25 | 24 | +1.9432 | $+37,087.74 | 60.97% | 0.0991 | pnl_top5_concentration |

## Next Decision

`observed_only_no_new_strategy_variable`.

- rank-notional is already accepted default-off; this experiment is a diagnostics closeout, not a new alpha rule
- hold-days 25 remains rejected because old_thin regressed in the fixed-window comparison
- tail concentration did not clearly improve enough to justify another nearby rank-profile retune
- old_thin state-surface evidence is still thin, so do not infer a new old-window-specific rule

## Production Impact

```json
{
  "alters_candidate_ranking": false,
  "alters_exits": false,
  "alters_orders": false,
  "alters_signal_generation": false,
  "alters_sizing": false,
  "backtester_adapter_changed": false,
  "diagnostic_only": true,
  "parity_test_added": false,
  "production_signal_path_changed": false,
  "replay_only": false,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}
```

No JavaScript was used.
