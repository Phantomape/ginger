# exp-20260524-029 Space Data/Defense Core-Pool Scout

Decision: `rejected_space_data_defense_core_pool`.

Single variable: add the governed Space data/defense cohort to the core replay universe.

## Trial Accounting

- trial_family: `governed_space_data_defense_candidate_pool`
- changed_variable: `space_data_defense_core_universe_membership`
- prior_trial_count: `5`
- multiple_testing_risk_bucket: `high`
- new_evidence_type: `canonical_aligned_observation_universe_ohlcv_current_governed_space_data_defense_records`

## Target Cohort

`BKSY`, `PL`, `RDW`

## Three-Window Result

| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| late_strong | 4.9354 | 4.2906 | -0.6448 | $113,719.84 | $104,647.47 | $-9,072.37 | 0.8182 | 1 |
| mid_weak | 2.1386 | 1.9227 | -0.2159 | $78,050.31 | $73,951.59 | $-4,098.72 | 0.8136 | 1 |
| old_thin | 0.5805 | 0.4426 | -0.1379 | $40,307.27 | $33,527.94 | $-6,779.33 | 0.7571 | 0 |

## Gate 4

```json
{
  "aggregate_ev_delta_positive": false,
  "aggregate_pnl_delta_positive": false,
  "improved_windows": [],
  "max_drawdown_worse": 0.0494,
  "max_drawdown_worse_guardrail": 0.005,
  "passed": false,
  "regressed_windows": [
    "late_strong",
    "mid_weak",
    "old_thin"
  ],
  "survival_guard_passed": true,
  "target_concentration": {
    "max_single_positive_pnl_share": null,
    "max_single_positive_pnl_share_guardrail": 0.5,
    "passed": false,
    "positive_pnl_hhi": null,
    "positive_pnl_hhi_guardrail": 0.45
  },
  "target_trade_count": 2,
  "target_trade_count_min": 6,
  "target_window_count_min": 2,
  "target_windows": [
    "late_strong",
    "mid_weak"
  ]
}
```

## Production Impact

Replay-only. No production watchlist, shared policy, run adapter, or order path changed. A positive replay would still need shared universe/taxonomy/risk constraints and parity tests before any live/default behavior changes.

No JavaScript was used.
