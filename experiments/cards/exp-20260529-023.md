# exp-20260529-023 Form4 Post-Drawdown Reclaim Candidate Pool

Decision: `rejected_form4_post_drawdown_reclaim`.

Single variable: a default-off paper candidate source admits PIT-safe Form 4 meaningful open-market purchases only when price is 8% to 35% below its prior 60-day high, has reclaimed the prior 20-day moving average, and has beaten SPY over five days. Selection is top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | +0.0000 | 0 | 0 |
| mid_weak | 2.1402 | 2.2560 | +0.1158 | $78,110.11 | $79,998.52 | $+1,888.41 | -0.0019 | 1 | 1 |
| old_thin | 0.5911 | 0.5911 | +0.0000 | $39,667.96 | $39,667.96 | $+0.00 | +0.0000 | 0 | 0 |

## Aggregate

- EV delta: `0.1158` (`0.014669`)
- PnL delta: `$1888.41` (`0.008041`)
- target trades: `1` across `1` windows
- max single positive share: `1.0`
- positive PnL HHI: `1.0`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "target_sample_too_small",
    "target_window_coverage_too_small",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 1.0,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 1.0,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 1,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "mid_weak"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 0,
  "windows_pnl_improved": 1,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
