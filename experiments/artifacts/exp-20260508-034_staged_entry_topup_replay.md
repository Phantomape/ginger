# exp-20260508-034 Staged Entry Top-up Replay

Decision: `rejected`.

## Hypothesis

Buying a conservative initial fraction of each accepted A/B signal and using the existing day-2 follow-through add-on to top up confirmed winners may improve expected value by reducing loser exposure while preserving upside in trades that quickly work.

## Best Variant

Best variant: `initial_75pct`.

| Window | EV Before | EV After | EV Delta | PnL Delta | Sharpe Daily Delta | Max DD Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| late_strong | 4.0674 | 3.1543 | -0.9131 | $-20,849.94 | +0.03 | -1.29% |
| mid_weak | 1.6195 | 1.2531 | -0.3664 | $-13,126.73 | -0.02 | -1.55% |
| old_thin | 0.3583 | 0.3097 | -0.0486 | $-4,906.66 | +0.07 | -2.14% |

## Aggregate

```json
{
  "after_ev_sum": 4.7171,
  "after_pnl_sum": 138793.6,
  "aggregate_ev_delta": -1.3281,
  "aggregate_ev_delta_pct": -0.219695,
  "aggregate_pnl_delta": -38883.33,
  "aggregate_pnl_delta_pct": -0.218843,
  "baseline_ev_sum": 6.0452,
  "baseline_pnl_sum": 177676.93,
  "ev_positive_windows": [],
  "ev_regressed_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "max_drawdown_delta_max": -0.0129,
  "pnl_positive_windows": [],
  "pnl_regressed_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "sharpe_daily_delta_max": 0.07,
  "trade_count_delta_sum": 0,
  "win_rate_regressions": []
}
```

## Production Parity

{
  "backtester_adapter_changed": false,
  "parity_test_added": false,
  "promotion_requirement_if_positive": "Implement staged initial shares and original_shares preservation in shared production/backtest policy, expose intended_shares in run.py, and add parity tests before live promotion.",
  "replay_only": true,
  "run_adapter_changed": false,
  "shared_policy_changed": false
}

## Anti-Repeat

Gate 4 failed. Staging initial entries reduced exposure to winners more than it helped avoid losers; do not retry nearby 50%-75% staged-entry fractions without a new discriminator for which entries should be staged.
