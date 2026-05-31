# exp-20260531-015 SEC Item 8.01 Inverse Candidate Pool

Decision: `rejected_sec_item801_inverse_candidate_pool`.

Single variable: PIT-safe SEC 8-K Item 8.01 positive-reaction events are isolated and evaluated as a default-off inverse paper candidate pool.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Inverse trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.3961 | +0.2333 | $117,072.92 | $119,118.59 | $+2,045.67 | -0.0011 | 4 | 6 |
| mid_weak | 2.1402 | 2.0538 | -0.0864 | $78,110.11 | $76,349.40 | $-1,760.71 | +0.0001 | 9 | 10 |
| old_thin | 0.5911 | 0.6108 | +0.0197 | $39,667.96 | $40,454.55 | $+786.59 | -0.0002 | 6 | 6 |

## Aggregate

- EV delta: `0.1666` (`0.021104`)
- PnL delta: `$1071.55` (`0.004563`)
- target trades: `19` across `3` windows
- max single positive share: `0.544282`
- positive PnL HHI: `0.386111`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "window_ev_regression",
    "window_pnl_regression",
    "target_sample_too_small",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0001,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.544282,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.386111,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 19,
  "target_trade_count_min": 20,
  "target_window_count_min": 3,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_improved": 2,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed.

Short borrow, locate, and gap-risk costs are not modeled, so any positive replay result is not live-activation evidence.

No JavaScript was used.
