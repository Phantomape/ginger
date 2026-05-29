# exp-20260529-015 SEC FD/Other 8-K Positive-Reaction Candidate Pool

Decision: `rejected_sec_fd_other_8k_positive_reaction`.

Single variable: a default-off paper candidate source that admits PIT-safe SEC 8-K Item 7.01 / 8.01 filings with positive same-day issuer reaction, liquidity, trend, and RS confirmation, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.0064 | -0.1564 | $117,072.92 | $115,885.97 | $-1,186.95 | +0.0011 | 5 | 8 |
| mid_weak | 2.1402 | 2.1189 | -0.0213 | $78,110.11 | $77,896.02 | $-214.09 | +0.0001 | 16 | 17 |
| old_thin | 0.5911 | 0.5508 | -0.0403 | $39,667.96 | $38,247.25 | $-1,420.71 | +0.0006 | 8 | 8 |

## Aggregate

- EV delta: `-0.218` (`-0.027616`)
- PnL delta: `$-2821.75` (`-0.012015`)
- target trades: `29` across `3` windows
- max single positive share: `0.272537`
- positive PnL HHI: `0.179229`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "failed_reasons": [
    "aggregate_ev_not_positive",
    "aggregate_pnl_not_positive",
    "window_ev_regression",
    "window_pnl_regression"
  ],
  "max_drawdown_worse": 0.0011,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.272537,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.179229,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 29,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 0,
  "windows_ev_regressed": 3,
  "windows_pnl_improved": 0,
  "windows_pnl_regressed": 3
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
