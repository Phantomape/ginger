# exp-20260529-011 SEC Item 2.02 Comovement Peer Transfer

Decision: `rejected_sec_item202_comovement_peer_transfer`.

Single variable: default-off paper candidates are SEC Item 2.02 peer-transfer rows whose same-sector peer had trailing 60-trading-day daily-return co-movement with the issuer.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.0085 | -0.1543 | $117,072.92 | $115,673.29 | $-1,399.63 | +0.0006 | 3 | 7 |
| mid_weak | 2.1402 | 2.3662 | +0.2260 | $78,110.11 | $82,158.45 | $+4,048.34 | -0.0014 | 5 | 7 |
| old_thin | 0.5911 | 0.6024 | +0.0113 | $39,667.96 | $40,156.71 | $+488.75 | -0.0003 | 8 | 21 |

## Aggregate

- EV delta: `0.083` (`0.010514`)
- PnL delta: `$3137.46` (`0.013359`)
- target trades: `16` across `3` windows
- max single positive share: `0.220801`
- positive PnL HHI: `0.160312`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small"
  ],
  "max_drawdown_worse": 0.0006,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.220801,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.160312,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 16,
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
