# exp-20260602-020 Sector Peer Moderate-Shock Candidate Pool

Decision: `rejected_sector_peer_moderate_shock_candidate_pool`.

Single variable: a default-off paper source admits liquid same-sector peers when the prior 1..5 trading-day peer-shock score is positive but below the strong bucket.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.4848 | +0.3220 | $117,072.92 | $120,283.39 | $+3,210.47 | -0.0019 | 10 | 26 |
| mid_weak | 2.1402 | 2.6892 | +0.5490 | $78,110.11 | $86,465.81 | $+8,355.70 | -0.0081 | 15 | 109 |
| old_thin | 0.5911 | 2.3279 | +1.7368 | $39,667.96 | $86,541.90 | $+46,873.94 | -0.0182 | 12 | 41 |

## Aggregate

- EV delta: `2.6078` (`0.330348`)
- PnL delta: `$58440.11` (`0.248839`)
- target trades: `37` across `3` windows
- max single positive share: `0.761365`
- positive PnL HHI: `0.602404`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "target_concentration_failed"
  ],
  "max_drawdown_worse": -0.0019,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.761365,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.602404,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 37,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 3,
  "windows_ev_regressed": 0,
  "windows_pnl_regressed": 0
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.

No JavaScript was used.
