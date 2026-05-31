# exp-20260531-013 Same-Industry Peer-Shock Candidate Pool

Decision: `rejected_same_industry_peer_shock_candidate_pool`.

Single variable: default-off paper candidates from liquid unshocked peers after strong positive same-industry OHLCV peer shocks.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.8074 | -1.3554 | $117,072.92 | $101,257.33 | $-15,815.59 | +0.0053 | 31 | 61 |
| mid_weak | 2.1402 | 3.4015 | +1.2613 | $78,110.11 | $99,754.90 | $+21,644.79 | -0.0209 | 48 | 92 |
| old_thin | 0.5911 | 0.7941 | +0.2030 | $39,667.96 | $46,989.43 | $+7,321.47 | -0.0053 | 22 | 35 |

## Aggregate

- EV delta: `0.1089` (`0.013795`)
- PnL delta: `$13150.67` (`0.055996`)
- target trades: `101` across `3` windows
- max single positive share: `0.506209`
- positive PnL HHI: `0.333694`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "drawdown_drift_too_high",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0053,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.506209,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.333694,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 101,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.

No JavaScript was used.
