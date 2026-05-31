# exp-20260531-021 Full-Universe Alpha-Score Market-Regime Safe Notional

Decision: `positive_replay_lead_not_promoted_requires_shared_adapter`.

Single variable: keep the exp-20260531-016 candidate source and market gate fixed, but reduce fixed paper notional from $10,000 to $4,000 per candidate.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 5.7091 | +0.5463 | $117,072.92 | $124,108.18 | $+7,035.26 | +0.0000 | 52 | 154 |
| mid_weak | 2.1402 | 2.8448 | +0.7046 | $78,110.11 | $90,603.09 | $+12,492.98 | -0.0024 | 62 | 287 |
| old_thin | 0.5911 | 0.9841 | +0.3930 | $39,667.96 | $52,910.24 | $+13,242.28 | -0.0062 | 37 | 174 |

## Aggregate

- EV delta: `1.6439` (`0.208244`)
- PnL delta: `$32770.52` (`0.139537`)
- target trades: `151` across `3` windows
- max single positive share: `0.274512`
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
    "ev_delta_sum": 1.6439,
    "max_drawdown_delta_max": 0.0,
    "max_single_positive_share": 0.274512,
    "pnl_delta_sum": 32770.52,
    "positive_hhi": 0.18724,
    "target_trades": 151
  },
  "current_safe_notional_0p40": {
    "ev_delta_sum": 1.6439,
    "max_drawdown_delta_max": 0.0,
    "max_single_positive_share": 0.274512,
    "pnl_delta_sum": 32770.52,
    "positive_hhi": 0.18724,
    "target_trades": 151
  },
  "exp016_market_regime_10k": {
    "decision": "rejected_full_universe_alpha_score_market_regime_candidate_pool",
    "ev_delta_sum": 4.1938,
    "experiment_id": "exp-20260531-016",
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
  "failed_reasons": [],
  "max_drawdown_worse": 0.0,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": true,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.274512,
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

Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, exit, LLM, or news behavior changed. A positive replay result still requires a shared default-off adapter and parity tests before activation.

No JavaScript was used.
