# exp-20260530-015 SEC Small Event-Family Burst Candidate Pool

Decision: `rejected_sec_small_event_family_burst`.

Single variable: a default-off paper candidate source that admits PIT-safe SEC filings from exactly two-ticker same-day same-event-family bursts with OHLCV confirmation, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.1640 | +0.0012 | $117,072.92 | $118,173.72 | $+1,100.80 | +0.0013 | 10 | 14 |
| mid_weak | 2.1402 | 2.1113 | -0.0289 | $78,110.11 | $77,624.07 | $-486.04 | -0.0005 | 10 | 17 |
| old_thin | 0.5911 | 0.6082 | +0.0171 | $39,667.96 | $40,280.36 | $+612.40 | -0.0010 | 14 | 23 |

## Aggregate

- EV delta: `-0.0106` (`-0.001343`)
- PnL delta: `$1227.16` (`0.005225`)
- target trades: `34` across `3` windows
- max single positive share: `0.553061`
- positive PnL HHI: `0.352842`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "aggregate_ev_not_positive",
    "ev_regressed_window",
    "pnl_regressed_window",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0013,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.553061,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.352842,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 34,
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
