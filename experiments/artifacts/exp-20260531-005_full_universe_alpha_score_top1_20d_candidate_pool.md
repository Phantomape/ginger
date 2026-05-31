# exp-20260531-005 Full-Universe Alpha-Score Top-1 Candidate Pool

Decision: `rejected_full_universe_alpha_score_top1_20d_candidate_pool`.

Single variable: a default-off paper source admits the liquid stock with the highest PIT full-universe alpha_score each signal day, top-1 per day, next-open entry, 20-trading-day exit.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 6.4530 | +1.2902 | $117,072.92 | $136,142.36 | $+19,069.44 | +0.0092 | 100 | 289 |
| mid_weak | 2.1402 | 5.5978 | +3.4576 | $78,110.11 | $129,876.98 | $+51,766.87 | -0.0225 | 109 | 503 |
| old_thin | 0.5911 | 3.0033 | +2.4122 | $39,667.96 | $100,109.57 | $+60,441.61 | +0.1332 | 121 | 530 |

## Aggregate

- EV delta: `7.16` (`0.907006`)
- PnL delta: `$131277.92` (`0.558984`)
- target trades: `330` across `3` windows
- max single positive share: `0.487462`
- positive PnL HHI: `0.298747`

## Gate 4

```json
{
  "aggregate_ev_delta_positive": true,
  "aggregate_pnl_delta_positive": true,
  "failed_reasons": [
    "drawdown_drift_too_high",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.1332,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.487462,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.298747,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 330,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.

No JavaScript was used.
