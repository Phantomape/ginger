# exp-20260529-010 Peer Earnings-Reaction Transfer

Decision: `rejected_peer_earnings_reaction_transfer`.

Single variable: a default-off paper candidate source that admits liquid same-sector peers after a positive SEC 8-K Item 2.02 issuer reaction, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.9749 | -0.1879 | $117,072.92 | $115,161.53 | $-1,911.39 | +0.0004 | 5 | 15 |
| mid_weak | 2.1402 | 2.3963 | +0.2561 | $78,110.11 | $82,633.16 | $+4,523.05 | -0.0021 | 7 | 12 |
| old_thin | 0.5911 | 0.6197 | +0.0286 | $39,667.96 | $40,235.19 | $+567.23 | +0.0016 | 11 | 28 |

## Aggregate

- EV delta: `0.0968` (`0.012262`)
- PnL delta: `$3178.89` (`0.013536`)
- target trades: `23` across `3` windows
- max single positive share: `0.31969`
- positive PnL HHI: `0.191372`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression"
  ],
  "max_drawdown_worse": 0.0016,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.31969,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.191372,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 23,
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
