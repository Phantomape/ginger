# exp-20260531-011 Full-Universe Alpha-Score Breadth-Aligned Candidate Pool

Decision: `rejected_full_universe_alpha_score_breadth_aligned_candidate_pool`.

Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile source fixed, but admit only candidates with alpha_score_components.breadth_alignment >= 0.65.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 6.5428 | +1.3800 | $117,072.92 | $134,346.17 | $+17,273.25 | -0.0106 | 46 | 148 |
| mid_weak | 2.1402 | 4.4900 | +2.3498 | $78,110.11 | $116,015.13 | $+37,905.02 | -0.0183 | 95 | 430 |
| old_thin | 0.5911 | 3.3471 | +2.7560 | $39,667.96 | $107,969.70 | $+68,301.74 | +0.0616 | 74 | 313 |

## Aggregate

- EV delta: `6.4858` (`0.821601`)
- PnL delta: `$123480.01` (`0.52578`)
- target trades: `215` across `3` windows
- max single positive share: `0.506887`
- positive PnL HHI: `0.311264`

## Prior Comparison

```json
{
  "cooldown": {
    "decision": "rejected_full_universe_alpha_score_cooldown_candidate_pool",
    "ev_delta_sum": 3.6871,
    "experiment_id": "exp-20260531-007",
    "max_drawdown_delta_max": 0.0342,
    "max_single_positive_share": 0.18746,
    "pnl_delta_sum": 70480.35,
    "positive_hhi": 0.103883,
    "target_trades": 200
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
  "current_breadth_aligned": {
    "ev_delta_sum": 6.4858,
    "max_drawdown_delta_max": 0.0616,
    "max_single_positive_share": 0.506887,
    "pnl_delta_sum": 123480.01,
    "positive_hhi": 0.311264,
    "target_trades": 215
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
    "drawdown_drift_too_high",
    "target_concentration_failed"
  ],
  "max_drawdown_worse": 0.0616,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.506887,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.311264,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 215,
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
