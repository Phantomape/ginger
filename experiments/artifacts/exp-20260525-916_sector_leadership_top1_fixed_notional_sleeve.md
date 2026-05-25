# exp-20260525-916 Sector-Leadership Top-1 Fixed-Notional Sleeve

Decision: `rejected_sector_leadership_top1_fixed_notional_sleeve`.

Single variable: a default-off paper sleeve admits at most one sector-leadership relative-strength candidate per day, enters at next open, and exits after ten trading days.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9600 | -0.2028 | $117,072.92 | $116,163.31 | $-909.61 | +0.0165 | 90 | 366 |
| mid_weak | 2.1402 | 5.9682 | +3.8280 | $78,110.11 | $132,043.29 | $+53,933.18 | -0.0299 | 116 | 843 |
| old_thin | 0.5911 | 1.0144 | +0.4233 | $39,667.96 | $50,473.57 | $+10,805.61 | +0.0773 | 103 | 511 |

## Aggregate

- EV delta: `4.0485` (`0.512851`)
- PnL delta: `$63829.18` (`0.271786`)
- target trades: `309` across `3` windows
- max single positive share: `0.46216`
- positive PnL HHI: `0.259838`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "max_drawdown_worse": 0.0773,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.46216,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.259838,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 309,
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
