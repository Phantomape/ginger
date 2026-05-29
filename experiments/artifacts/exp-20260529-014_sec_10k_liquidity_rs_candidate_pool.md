# exp-20260529-014 SEC 10-K Liquidity + RS Candidate Pool

Decision: `rejected_sec_10k_liquidity_rs`.

Single variable: a default-off paper candidate source that admits PIT-safe SEC 10-K filings with liquidity, trend, and RS confirmation, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1361 | -0.0267 | $117,072.92 | $116,726.21 | $-346.71 | +0.0000 | 2 | 2 |
| mid_weak | 2.1402 | 2.1785 | +0.0383 | $78,110.11 | $78,930.70 | $+820.59 | +0.0000 | 1 | 1 |
| old_thin | 0.5911 | 0.6196 | +0.0285 | $39,667.96 | $40,758.01 | $+1,090.05 | -0.0037 | 9 | 9 |

## Aggregate

- EV delta: `0.0401` (`0.00508`)
- PnL delta: `$1563.93` (`0.006659`)
- target trades: `12` across `3` windows
- max single positive share: `0.285136`
- positive PnL HHI: `0.184224`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "ev_regressed_window",
    "pnl_regressed_window",
    "target_sample_too_small"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.285136,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.184224,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 12,
  "target_trade_count_min": 20,
  "target_window_count_min": 2,
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
