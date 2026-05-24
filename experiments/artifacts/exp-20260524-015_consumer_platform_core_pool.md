# exp-20260524-015 Consumer Digital Platform Core-Pool Scout

Decision: `rejected_consumer_platform_core_pool`.

Single variable: add the governed consumer digital platform pilot cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_consumer_platform_candidate_pool`
- changed_variable: `consumer_platform_core_universe_membership`
- prior_trial_count: `4`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_consumer_platform_records`

## Target Cohort

`HOOD`, `RBLX`, `SOFI`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.1940 | -0.7414 | $113,719.84 | $104,072.28 | $-9,647.56 | 0.8113 | 1 |
| mid_weak | 2.1386 | 2.7013 | +0.5627 | $78,050.31 | $91,880.51 | $+13,830.20 | 0.7636 | 1 |
| old_thin | 0.5805 | -0.0004 | -0.5809 | $40,307.27 | $-193.06 | $-40,500.33 | 0.7297 | 4 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "improved_windows": [
    "mid_weak"
  ],
  "max_drawdown_worse": 0.0665,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "late_strong",
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": 0.631848,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": 0.534768,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 6,
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

Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay would still need shared pilot universe, sector taxonomy, risk constraints, and parity tests before any live/default behavior changes.

No JavaScript was used.
