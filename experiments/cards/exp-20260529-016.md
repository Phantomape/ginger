# exp-20260529-016 SEC Item 1.01 Positive-Reaction Candidate Pool

Decision: `rejected_sec_item101_positive_reaction`.

Single variable: a default-off paper candidate source that admits PIT-safe SEC 8-K Item 1.01 material-agreement filings with positive same-day issuer reaction, liquidity, trend, and RS confirmation, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1628 | +0.0000 | $117,072.92 | $117,072.92 | $+0.00 | +0.0000 | 0 | 0 |
| mid_weak | 2.1402 | 2.1402 | +0.0000 | $78,110.11 | $78,110.11 | $+0.00 | +0.0000 | 0 | 0 |
| old_thin | 0.5911 | 0.5107 | -0.0804 | $39,667.96 | $36,480.02 | $-3,187.94 | +0.0036 | 1 | 1 |

## Aggregate

- EV delta: `-0.0804` (`-0.010185`)
- PnL delta: `$-3187.94` (`-0.013574`)
- target trades: `1` across `1` windows
- max single positive share: `None`
- positive PnL HHI: `None`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "failed_reasons": [
    "aggregate_ev_not_positive",
    "aggregate_pnl_not_positive",
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small",
    "target_window_coverage_too_small",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0036,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": null,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": null,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 1,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "old_thin"
  ],
  "windows_ev_improved": 0,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
