# exp-20260529-001 VWAP Reclaim Relative-Strength Paper Sleeve

Decision: `rejected_vwap_reclaim_rs_paper_sleeve`.

Single variable: a default-off paper source admits stock-only 20-day VWAP reclaim candidates with positive 20-day relative strength versus SPY, top-1 per day, next-open entry, ten-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.7063 | -1.4565 | $117,072.92 | $98,053.26 | $-19,019.66 | +0.0022 | 62 | 117 |
| mid_weak | 2.1402 | 2.7520 | +0.6118 | $78,110.11 | $89,059.29 | $+10,949.18 | -0.0097 | 59 | 120 |
| old_thin | 0.5911 | 0.5207 | -0.0704 | $39,667.96 | $36,669.66 | $-2,998.30 | +0.0434 | 79 | 160 |

## Aggregate

- EV delta: `-0.9151` (`-0.115922`)
- PnL delta: `$-11068.78` (`-0.047131`)
- target trades: `200` across `3` windows
- max single positive share: `0.344117`
- positive PnL HHI: `0.176066`

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
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0434,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.344117,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.176066,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 200,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 1,
  "windows_ev_regressed": 2,
  "windows_pnl_regressed": 2
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.

No JavaScript was used.
