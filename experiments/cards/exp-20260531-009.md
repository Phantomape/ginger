# exp-20260531-009 Full-Universe Alpha-Score Resilient-Rank Candidate Pool

Decision: `rejected_full_universe_alpha_score_resilient_rank_candidate_pool`.

Single variable: keep the exp-20260531-005 full-universe alpha_score top-decile source fixed, but rank same-day candidates by `risk_adjusted_alpha_score = alpha_score * (0.50 + prior_20d_drawdown_volatility_resilience_score)`.

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.1136 | -1.0492 | $117,072.92 | $106,571.73 | $-10,501.19 | +0.0291 | 100 | 287 |
| mid_weak | 2.1402 | 3.6149 | +1.4747 | $78,110.11 | $99,860.09 | $+21,749.98 | -0.0214 | 109 | 503 |
| old_thin | 0.5911 | 2.7541 | +2.1630 | $39,667.96 | $95,634.04 | $+55,966.08 | +0.0817 | 121 | 530 |

## Aggregate

- EV delta: `2.5885` (`0.327903`)
- PnL delta: `$67214.87` (`0.286202`)
- target trades: `330` across `3` windows
- max single positive share: `0.608462`
- positive PnL HHI: `0.38296`

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
  "current_resilient_rank": {
    "ev_delta_sum": 2.5885,
    "max_drawdown_delta_max": 0.0817,
    "max_single_positive_share": 0.608462,
    "pnl_delta_sum": 67214.87,
    "positive_hhi": 0.38296,
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
  "max_drawdown_worse": 0.0817,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.608462,
    "max_single_positive_pnl_share_guardrail": 0.4,
    "passed": false,
    "positive_pnl_hhi": 0.38296,
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
