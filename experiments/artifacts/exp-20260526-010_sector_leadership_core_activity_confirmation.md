# exp-20260526-010 Sector-Leadership Core-Activity Confirmation

Decision: `rejected_sector_leadership_core_activity_confirmation`.

Single variable: keep the sector-leadership candidate source fixed, but admit paper candidates only when same-date core trend/breakout activity is present.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Confirmed candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.0865 | -0.0763 | $117,072.92 | $117,473.71 | $+400.79 | +0.0035 | 10 | 51 |
| mid_weak | 2.1402 | 2.8838 | +0.7436 | $78,110.11 | $91,262.47 | $+13,152.36 | -0.0011 | 20 | 122 |
| old_thin | 0.5911 | 0.6863 | +0.0952 | $39,667.96 | $42,625.82 | $+2,957.86 | -0.0009 | 17 | 76 |

## Aggregate

- EV delta: `0.7625` (`0.096591`)
- PnL delta: `$16511.01` (`0.070304`)
- target trades: `47` across `3` windows
- max single positive share: `0.266596`
- positive PnL HHI: `0.175129`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0035,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.266596,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.175129,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 47,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
