# exp-20260523-003 AI Optical Connectivity Core-Pool Scout

Decision: `rejected_ai_optical_connectivity_core_pool`.

Single variable: add the governed optical-connectivity cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_ai_infra_candidate_pool`
- changed_variable: `ai_optical_connectivity_core_universe_membership`
- prior_trial_count: `4`
- multiple_testing_risk_bucket: `moderate`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv`

## Target Cohort

`CIEN`, `COHR`, `FN`, `GLW`, `LITE`, `MRVL`, `MTSI`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 5.1628 | 4.0307 | -1.1321 | $117,072.92 | $106,351.31 | $-10,721.61 | 0.8125 | 5 |
| mid_weak | 2.1402 | 1.7552 | -0.3850 | $78,110.11 | $68,028.10 | $-10,082.01 | 0.8333 | 5 |
| old_thin | 0.5888 | 0.5174 | -0.0714 | $39,517.10 | $35,677.57 | $-3,839.53 | 0.8378 | 5 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "improved_windows": [],
  "max_drawdown_worse": 0.0091,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.526602,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "top5_positive_pnl_share": 1.0,
    "top5_positive_pnl_share_guardrail": 0.8
  },
  "target_trade_count": 15,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ]
}
```

## Production Impact

No production watchlist, shared policy, run adapter, or order path changed. A positive result requires shared universe/taxonomy implementation and parity tests before any live/default behavior changes.

No JavaScript was used.
