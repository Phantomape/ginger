# exp-20260529-019 SEC Item 5.02 Positive-Reaction Candidate Pool

Decision: `rejected_sec_item502_positive_reaction`.

Single variable: a default-off paper candidate source that admits PIT-safe SEC 8-K Item 5.02 leadership-change filings with positive same-day issuer reaction, liquidity, trend, and RS confirmation, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.8696 | -0.2932 | $117,072.92 | $113,509.99 | $-3,562.93 | +0.0005 | 8 | 9 |
| mid_weak | 2.1402 | 2.1345 | -0.0057 | $78,110.11 | $77,902.75 | $-207.36 | +0.0000 | 3 | 3 |
| old_thin | 0.5911 | 0.6006 | +0.0095 | $39,667.96 | $40,036.51 | $+368.55 | -0.0002 | 2 | 2 |

## Aggregate

- EV delta: `-0.2894` (`-0.03666`)
- PnL delta: `$-3401.74` (`-0.014485`)
- target trades: `13` across `3` windows
- max single positive share: `0.406186`
- positive PnL HHI: `0.356831`

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
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0005,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.406186,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.356831,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 13,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_improved": 1,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
