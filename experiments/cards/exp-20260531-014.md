# exp-20260531-014 Full-Universe Alpha-Score Low-Volume Candidate Pool

Decision: `rejected_full_universe_alpha_score_low_volume_candidate_pool`.

Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile source fixed, but admit only candidates with avg_dollar_volume_20d at or below that signal day's top-decile median.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 2.8643 | -2.2985 | $117,072.92 | $91,216.51 | $-25,856.41 | +0.0349 | 100 | 176 |
| mid_weak | 2.1402 | 5.7447 | +3.6045 | $78,110.11 | $129,968.07 | $+51,857.96 | -0.0243 | 109 | 294 |
| old_thin | 0.5911 | 5.3308 | +4.7397 | $39,667.96 | $141,400.07 | $+101,732.11 | +0.0555 | 121 | 315 |

## Aggregate

- EV delta: `6.0457` (`0.76585`)
- PnL delta: `$127733.66` (`0.543892`)
- target trades: `330` across `3` windows
- max single positive share: `0.524945`
- positive PnL HHI: `0.32495`

## Prior Comparison

```json
{
  "breadth_aligned": {
    "decision": "rejected_full_universe_alpha_score_breadth_aligned_candidate_pool",
    "ev_delta_sum": 6.4858,
    "experiment_id": "exp-20260531-011",
    "max_drawdown_delta_max": 0.0616,
    "max_single_positive_share": 0.506887,
    "pnl_delta_sum": 123480.01,
    "positive_hhi": 0.311264,
    "target_trades": 215
  },
  "cost_liquidity": {
    "decision": "rejected_full_universe_alpha_score_cost_liquidity_candidate_pool",
    "ev_delta_sum": 6.0403,
    "experiment_id": "exp-20260531-008",
    "max_drawdown_delta_max": 0.1126,
    "max_single_positive_share": 0.515024,
    "pnl_delta_sum": 116441.9,
    "positive_hhi": 0.323382,
    "target_trades": 330
  },
  "current_low_volume_bucket": {
    "ev_delta_sum": 6.0457,
    "max_drawdown_delta_max": 0.0555,
    "max_single_positive_share": 0.524945,
    "pnl_delta_sum": 127733.66,
    "positive_hhi": 0.32495,
    "target_trades": 330
  },
  "raw_top1": {
    "decision": "rejected_full_universe_alpha_score_top1_20d_candidate_pool",
    "ev_delta_sum": 6.6893,
    "experiment_id": "exp-20260531-005",
    "max_drawdown_delta_max": 0.1332,
    "max_single_positive_share": 0.502709,
    "pnl_delta_sum": 125182.69,
    "positive_hhi": 0.31675,
    "target_trades": 330
  },
  "resilient_rank": {
    "decision": "rejected_full_universe_alpha_score_resilient_rank_candidate_pool",
    "ev_delta_sum": 2.5885,
    "experiment_id": "exp-20260531-009",
    "max_drawdown_delta_max": 0.0817,
    "max_single_positive_share": 0.608462,
    "pnl_delta_sum": 67214.87,
    "positive_hhi": 0.38296,
    "target_trades": 330
  }
}
```

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
  "max_drawdown_worse": 0.0555,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.524945,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.32495,
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
  "windows_ev_improved": 2,
  "windows_ev_regressed": 1,
  "windows_pnl_regressed": 1
}
```

## Production Impact

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result is not promoted without a shared default-off adapter and parity tests.

No JavaScript was used.
