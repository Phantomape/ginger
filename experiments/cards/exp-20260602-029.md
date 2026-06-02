# exp-20260602-029 Exact-Industry Moderate Peer-Shock Candidate Pool

Decision: `rejected_industry_peer_moderate_shock_candidate_pool`.

Single variable: default-off paper candidates from liquid unshocked peers after moderate positive exact-industry OHLCV peer shocks.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.8541 | -0.3087 | $117,072.92 | $113,683.91 | $-3,389.01 | +0.0011 | 8 | 13 |
| mid_weak | 2.1402 | 2.3394 | +0.1992 | $78,110.11 | $80,669.50 | $+2,559.39 | -0.0066 | 13 | 30 |
| old_thin | 0.5911 | 0.5953 | +0.0042 | $39,667.96 | $39,945.52 | $+277.56 | -0.0009 | 6 | 10 |

## Aggregate

- EV delta: `-0.1053` (`-0.013339`)
- PnL delta: `$-552.06` (`-0.002351`)
- target trades: `27` across `3` windows
- max single positive share: `0.74349`
- positive PnL HHI: `0.580638`

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
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0011,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.74349,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.580638,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 27,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.

No JavaScript was used.
