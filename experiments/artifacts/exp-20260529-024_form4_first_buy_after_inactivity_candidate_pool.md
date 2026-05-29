# exp-20260529-024 Form4 First-Buy-After-Inactivity Candidate Pool

Decision: `rejected_form4_first_buy_after_inactivity`.

Single variable: a default-off paper candidate source admits PIT-safe Form 4 meaningful open-market purchases only when the ticker had no prior meaningful Form 4 buy for at least 120 calendar days. Selection is top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.2388 | +0.0760 | $117,072.92 | $117,986.31 | $+913.39 | -0.0001 | 5 | 5 |
| mid_weak | 2.1402 | 2.2927 | +0.1525 | $78,110.11 | $80,731.30 | $+2,621.19 | -0.0018 | 5 | 5 |
| old_thin | 0.5911 | 0.5620 | -0.0291 | $39,667.96 | $38,488.73 | $-1,179.23 | +0.0077 | 1 | 1 |

## Aggregate

- EV delta: `0.1994` (`0.025259`)
- PnL delta: `$2355.35` (`0.010029`)
- target trades: `11` across `3` windows
- max single positive share: `0.541255`
- positive PnL HHI: `0.354739`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small",
    "drawdown_guardrail_failed",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0077,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.541255,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.354739,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 11,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
