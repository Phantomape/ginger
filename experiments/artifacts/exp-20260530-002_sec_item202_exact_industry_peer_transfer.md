# exp-20260530-002 SEC Item 2.02 Exact-Industry Peer Transfer

Decision: `rejected_sec_item202_exact_industry_peer_transfer`.

Single variable: default-off paper candidates are SEC Item 2.02 peer-transfer rows whose peer has the same reference industry string as the positive-reaction issuer.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.0635 | -0.0993 | $117,072.92 | $116,673.42 | $-399.50 | +0.0006 | 4 | 7 |
| mid_weak | 2.1402 | 2.1430 | +0.0028 | $78,110.11 | $78,206.95 | $+96.84 | +0.0001 | 2 | 2 |
| old_thin | 0.5911 | 0.5858 | -0.0053 | $39,667.96 | $39,584.90 | $-83.06 | +0.0001 | 4 | 5 |

## Aggregate

- EV delta: `-0.1018` (`-0.012896`)
- PnL delta: `$-385.72` (`-0.001642`)
- target trades: `10` across `3` windows
- max single positive share: `0.487061`
- positive PnL HHI: `0.413994`

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
  "max_drawdown_worse": 0.0006,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.487061,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.413994,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 10,
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
