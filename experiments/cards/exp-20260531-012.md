# exp-20260531-012 Same-Sector Peer-Shock Candidate Pool

Decision: `rejected_same_sector_peer_shock_candidate_pool`.

Single variable: default-off paper candidates from liquid unshocked peers after strong positive same-sector OHLCV peer shocks.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 3.7675 | -1.3953 | $117,072.92 | $101,548.96 | $-15,523.96 | +0.0160 | 42 | 144 |
| mid_weak | 2.1402 | 3.3492 | +1.2090 | $78,110.11 | $96,238.92 | $+18,128.81 | -0.0206 | 56 | 357 |
| old_thin | 0.5911 | 0.8370 | +0.2459 | $39,667.96 | $47,830.89 | $+8,162.93 | +0.0360 | 45 | 198 |

## Aggregate

- EV delta: `0.0596` (`0.00755`)
- PnL delta: `$10767.78` (`0.045849`)
- target trades: `143` across `3` windows
- max single positive share: `0.389272`
- positive PnL HHI: `0.308132`

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
  "max_drawdown_worse": 0.036,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.389272,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.308132,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 143,
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
