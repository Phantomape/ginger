# exp-20260531-016 Full-Universe Alpha-Score Market-Regime Candidate Pool

Decision: `rejected_full_universe_alpha_score_market_regime_candidate_pool`.

Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile source fixed, but admit candidates only when SPY is above its 50-day moving average and IWM 20-day return is at least SPY 20-day return.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 6.4233 | +1.2605 | $117,072.92 | $134,661.10 | $+17,588.18 | +0.0106 | 52 | 154 |
| mid_weak | 2.1402 | 3.9909 | +1.8507 | $78,110.11 | $109,342.53 | $+31,232.42 | -0.0057 | 62 | 287 |
| old_thin | 0.5911 | 1.6737 | +1.0826 | $39,667.96 | $72,773.66 | $+33,105.70 | -0.0063 | 37 | 174 |

## Aggregate

- EV delta: `4.1938` (`0.531258`)
- PnL delta: `$81926.3` (`0.348844`)
- target trades: `151` across `3` windows
- max single positive share: `0.274511`
- positive PnL HHI: `0.18724`

## Prior Alpha-Score Variants

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
  "current_market_regime": {
    "ev_delta_sum": 4.1938,
    "max_drawdown_delta_max": 0.0106,
    "max_single_positive_share": 0.274511,
    "pnl_delta_sum": 81926.3,
    "positive_hhi": 0.18724,
    "target_trades": 151
  },
  "low_volume_bucket": {
    "decision": "rejected_full_universe_alpha_score_low_volume_candidate_pool",
    "ev_delta_sum": 6.0457,
    "experiment_id": "exp-20260531-014",
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
    "drawdown_drift_too_high"
  ],
  "max_drawdown_worse": 0.0106,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.274511,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": true,
    "positive_pnl_hhi": 0.18724,
    "positive_pnl_hhi_guardrail": 0.3
  },
  "target_trade_count": 151,
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
