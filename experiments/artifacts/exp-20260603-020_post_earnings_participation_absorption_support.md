# exp-20260603-020 Post-Earnings Participation-Absorption Support

Decision: `rejected_post_earnings_participation_absorption_support`.

Single variable: already-selected `POST_EARNINGS_UNDERPRICED_DRIFT_PAPER` candidates with `signal_day_dollar_volume / avg_dollar_volume_20d >= 1.25` receive `1.05x` paper notional.

Baseline: `exp-20260603-004` accepted after metrics.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Supported trades | Participation dPnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.5209 | 5.5402 | +0.0193 | $120,282.89 | $120,443.41 | $+160.52 | -0.0001 | 5 | 5 | $+160.50 |
| mid_weak | 2.1948 | 2.1945 | -0.0003 | $78,947.80 | $78,944.34 | $-3.46 | +0.0000 | 9 | 8 | $-3.45 |
| old_thin | 0.5982 | 0.5983 | +0.0001 | $39,878.58 | $39,889.10 | $+10.52 | -0.0001 | 6 | 6 | $+10.53 |

## Aggregate

- EV delta: `0.0191` (`0.002297`)
- PnL delta: `$167.58` (`0.000701`)
- target trades: `20`
- supported trades: `19` across `['late_strong', 'mid_weak', 'old_thin']`
- target max single positive share: `0.313306`
- target positive PnL HHI: `0.196683`
- supported max single positive incremental share: `0.339859`
- supported positive incremental HHI: `0.224251`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "mid_weak_ev_not_improved_vs_exp004",
    "mid_weak_pnl_not_improved_vs_exp004",
    "window_ev_regression",
    "window_pnl_regression"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.313306,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": true,
    "positive_pnl_hhi": 0.196683,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 20,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay scout only. No shared adapter, backtester adapter, run adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior was changed. A positive result would need shared-adapter promotion before being retained.

No JavaScript was used.
