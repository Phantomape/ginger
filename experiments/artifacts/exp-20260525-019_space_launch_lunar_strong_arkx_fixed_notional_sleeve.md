# exp-20260525-019 Space Launch/Lunar Strong-ARKX Fixed-Notional Sleeve

Decision: `rejected_space_launch_lunar_strong_arkx_fixed_notional_sleeve`.

Single variable: route the governed launch/lunar Space cohort into an additive fixed-notional default-off paper sleeve only when prior-close ARKX 20d momentum leads SPY by at least 5 percentage points.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Target trades | Filtered |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.9354 | +0.0000 | $113,719.84 | $113,719.84 | $+0.00 | +0.0000 | 0 | 1 |
| mid_weak | 2.1386 | 2.2016 | +0.0630 | $78,050.31 | $79,483.58 | $+1,433.27 | +0.0000 | 2 | 0 |
| old_thin | 0.5805 | 0.6677 | +0.0872 | $40,307.27 | $43,360.55 | $+3,053.28 | -0.0021 | 1 | 0 |

## Aggregate

- EV delta: `0.1502`
- PnL delta: `$4486.55`
- target trades: `3`
- max single positive share: `1.0`
- positive PnL HHI: `1.0`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 1.0,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 1.0,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 3,
  "target_trade_count_min": 4,
  "target_window_count_min": 2,
  "target_windows": [
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
