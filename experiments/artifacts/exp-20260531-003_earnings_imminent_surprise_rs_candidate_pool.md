# exp-20260531-003 Earnings-Imminent Surprise/RS Candidate Pool

Decision: `rejected_earnings_imminent_surprise_rs_candidate_pool`.

Single variable: a default-off paper candidate source using canonical earnings snapshots plus OHLCV confirmation for the 1-7 day pre-earnings window, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.9153 | -1.2475 | $117,072.92 | $100,913.69 | $-16,159.23 | +0.0078 | 45 | 70 |
| mid_weak | 2.1402 | 5.2510 | +3.1108 | $78,110.11 | $121,546.94 | $+43,436.83 | -0.0149 | 53 | 87 |
| old_thin | 0.5911 | 2.0983 | +1.5072 | $39,667.96 | $79,479.43 | $+39,811.47 | +0.0282 | 57 | 123 |

## Aggregate

- EV delta: `3.3705` (`0.426964`)
- PnL delta: `$67089.07` (`0.285667`)
- target trades: `155` across `3` windows
- max single positive share: `0.262583`
- positive PnL HHI: `0.165501`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0282,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.262583,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.165501,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 155,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity test.

No JavaScript was used.
