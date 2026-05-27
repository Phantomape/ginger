# exp-20260527-012 Sector-Leadership Same-Sector Core Activity

Decision: `rejected_sector_leadership_same_sector_core_activity`.

Single variable: keep the sector-leadership candidate source fixed, but admit paper candidates only when same-date accepted core trend/breakout activity is present in the same sector.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Confirmed candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1049 | -0.0579 | $117,072.92 | $116,545.62 | $-527.30 | +0.0002 | 1 | 17 |
| mid_weak | 2.1402 | 2.2593 | +0.1191 | $78,110.11 | $80,690.64 | $+2,580.53 | +0.0000 | 10 | 48 |
| old_thin | 0.5911 | 0.6227 | +0.0316 | $39,667.96 | $40,698.95 | $+1,030.99 | -0.0007 | 6 | 25 |

## Aggregate

- EV delta: `0.0928` (`0.011756`)
- PnL delta: `$3084.22` (`0.013133`)
- target trades: `17` across `3` windows
- max single positive share: `0.249166`
- positive PnL HHI: `0.169293`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0002,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.249166,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.169293,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 17,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
